package com.jovi.s12sound;

import android.app.Activity;
import android.os.Bundle;
import android.os.SystemClock;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Base64;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;

/** Minimal C/synthetic v0.8 controller; it doesn't render audio on Android. */
public final class MainActivity extends Activity {
    private static final String DEFAULT_ENDPOINT = "ws://10.0.2.2:8765/state";
    private final ScheduledExecutorService sender = Executors.newSingleThreadScheduledExecutor();
    private final SimpleWebSocketClient socket = new SimpleWebSocketClient();
    private EditText endpoint;
    private TextView status;
    private ScheduledFuture<?> stateTask;
    private volatile boolean running;
    private volatile String activeEndpoint = DEFAULT_ENDPOINT;
    private long lastAcknowledgementMs;

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        int padding = (int) (16 * getResources().getDisplayMetrics().density);
        layout.setPadding(padding, padding, padding, padding);

        endpoint = new EditText(this);
        endpoint.setHint("PC WebSocket endpoint");
        endpoint.setText(DEFAULT_ENDPOINT);
        layout.addView(endpoint);
        layout.addView(button("Start", view -> start()));
        layout.addView(button("Stop", view -> stop()));
        layout.addView(button("Send Vehicle State", view -> sendOnce()));
        status = new TextView(this);
        status.setText("Stopped. C/synthetic protocol only.");
        layout.addView(status);
        setContentView(layout);
    }

    private Button button(String label, View.OnClickListener listener) {
        Button button = new Button(this);
        button.setText(label);
        button.setOnClickListener(listener);
        return button;
    }

    private String stateJson() {
        double timestamp = SystemClock.elapsedRealtimeNanos() / 1_000_000_000.0;
        return String.format(
                java.util.Locale.US,
                "{\"timestamp\":%.6f,\"speed\":80,\"acceleration\":1.2,\"rpm\":3200,\"load\":0.6,\"throttle\":0.6}",
                timestamp
        );
    }

    private void start() {
        if (running) {
            return;
        }
        activeEndpoint = endpoint.getText().toString().trim();
        running = true;
        stateTask = sender.scheduleAtFixedRate(() -> sendState(true), 0, 10, TimeUnit.MILLISECONDS);
        show("Sending C/synthetic state at 100 Hz");
    }

    private void stop() {
        running = false;
        if (stateTask != null) {
            stateTask.cancel(false);
            stateTask = null;
        }
        socket.close();
        show("Stopped");
    }

    private void sendOnce() {
        activeEndpoint = endpoint.getText().toString().trim();
        sender.execute(() -> sendState(false));
    }

    private void sendState(boolean fromSchedule) {
        if (fromSchedule && !running) {
            return;
        }
        try {
            socket.connect(activeEndpoint);
            String acknowledgement = socket.sendAndReceive(stateJson());
            long now = SystemClock.elapsedRealtime();
            if (now - lastAcknowledgementMs >= 500) {
                lastAcknowledgementMs = now;
                show("Runtime acknowledgement: " + acknowledgement);
            }
        } catch (IOException exception) {
            if (fromSchedule) {
                running = false;
                if (stateTask != null) {
                    stateTask.cancel(false);
                    stateTask = null;
                }
            }
            socket.close();
            show("Runtime unavailable: " + exception.getMessage());
        }
    }

    private void show(String value) {
        runOnUiThread(() -> status.setText(value));
    }

    @Override
    protected void onDestroy() {
        stop();
        sender.shutdownNow();
        super.onDestroy();
    }

    /** Small ws:// text client for the localhost-only demo; no external SDK is used. */
    private static final class SimpleWebSocketClient {
        private static final int SOCKET_TIMEOUT_MS = 2000;
        private final SecureRandom random = new SecureRandom();
        private final Object stateLock = new Object();
        private Socket socket;
        private InputStream input;
        private OutputStream output;
        private String endpoint;
        private long closeGeneration;

        void connect(String requestedEndpoint) throws IOException {
            Socket previous;
            long expectedGeneration;
            synchronized (stateLock) {
                if (socket != null && socket.isConnected() && !socket.isClosed() && requestedEndpoint.equals(endpoint)) {
                    return;
                }
                previous = detachLocked();
                expectedGeneration = ++closeGeneration;
            }
            closeQuietly(previous);
            URI uri = URI.create(requestedEndpoint);
            if (!"ws".equals(uri.getScheme()) || uri.getHost() == null) {
                throw new IOException("Only ws:// endpoints are supported");
            }
            Socket candidate = new Socket();
            try {
                candidate.connect(new InetSocketAddress(uri.getHost(), uri.getPort() < 0 ? 80 : uri.getPort()), SOCKET_TIMEOUT_MS);
                candidate.setSoTimeout(SOCKET_TIMEOUT_MS);
                InputStream candidateInput = candidate.getInputStream();
                OutputStream candidateOutput = candidate.getOutputStream();
                byte[] nonce = new byte[16];
                random.nextBytes(nonce);
                String key = Base64.getEncoder().encodeToString(nonce);
                String path = uri.getRawPath() == null || uri.getRawPath().isEmpty() ? "/state" : uri.getRawPath();
                String request = "GET " + path + " HTTP/1.1\r\n"
                        + "Host: " + uri.getHost() + ":" + (uri.getPort() < 0 ? 80 : uri.getPort()) + "\r\n"
                        + "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                        + "Sec-WebSocket-Key: " + key + "\r\nSec-WebSocket-Version: 13\r\n\r\n";
                candidateOutput.write(request.getBytes(StandardCharsets.US_ASCII));
                candidateOutput.flush();
                if (!readHttpHeader(candidateInput).startsWith("HTTP/1.1 101")) {
                    throw new IOException("WebSocket handshake rejected");
                }
                synchronized (stateLock) {
                    if (closeGeneration != expectedGeneration) {
                        throw new IOException("WebSocket closed during connect");
                    }
                    socket = candidate;
                    input = candidateInput;
                    output = candidateOutput;
                    endpoint = requestedEndpoint;
                }
            } catch (IOException exception) {
                closeQuietly(candidate);
                throw exception;
            }
        }

        String sendAndReceive(String text) throws IOException {
            InputStream activeInput;
            OutputStream activeOutput;
            synchronized (stateLock) {
                if (socket == null) {
                    throw new IOException("WebSocket is not connected");
                }
                activeInput = input;
                activeOutput = output;
            }
            byte[] payload = text.getBytes(StandardCharsets.UTF_8);
            if (payload.length >= 126) {
                throw new IOException("Demo packet too large");
            }
            byte[] mask = new byte[4];
            random.nextBytes(mask);
            activeOutput.write(0x81);
            activeOutput.write(0x80 | payload.length);
            activeOutput.write(mask);
            for (int index = 0; index < payload.length; index++) {
                activeOutput.write(payload[index] ^ mask[index % mask.length]);
            }
            activeOutput.flush();
            return readTextFrame(activeInput);
        }

        void close() {
            Socket active;
            synchronized (stateLock) {
                active = detachLocked();
                closeGeneration++;
            }
            closeQuietly(active);
        }

        private Socket detachLocked() {
            Socket active = socket;
            socket = null;
            input = null;
            output = null;
            endpoint = null;
            return active;
        }

        private static void closeQuietly(Socket active) {
            if (active == null) {
                return;
            }
            try {
                active.close();
            } catch (IOException ignored) {
                // Closing a local demo connection is best effort.
            }
        }

        private static String readHttpHeader(InputStream activeInput) throws IOException {
            ByteArrayOutputStream header = new ByteArrayOutputStream();
            int previous = 0;
            int current;
            while ((current = activeInput.read()) >= 0) {
                header.write(current);
                if (previous == '\r' && current == '\n' && header.size() >= 4) {
                    byte[] bytes = header.toByteArray();
                    int length = bytes.length;
                    if (bytes[length - 4] == '\r' && bytes[length - 3] == '\n') {
                        return header.toString(StandardCharsets.US_ASCII.name());
                    }
                }
                previous = current;
            }
            throw new IOException("WebSocket handshake ended early");
        }

        private static String readTextFrame(InputStream activeInput) throws IOException {
            int first = activeInput.read();
            int second = activeInput.read();
            if (first < 0 || second < 0 || (first & 0x0F) != 0x1) {
                throw new IOException("Expected a WebSocket text frame");
            }
            int length = second & 0x7F;
            if (length == 126) {
                byte[] extendedLength = readFully(activeInput, 2);
                length = (extendedLength[0] & 0xFF) << 8 | (extendedLength[1] & 0xFF);
            }
            if (length < 0 || length > 8192) {
                throw new IOException("Invalid WebSocket frame length");
            }
            if ((second & 0x80) != 0) {
                readFully(activeInput, 4);
            }
            return new String(readFully(activeInput, length), StandardCharsets.UTF_8);
        }

        private static byte[] readFully(InputStream activeInput, int length) throws IOException {
            byte[] bytes = new byte[length];
            int offset = 0;
            while (offset < length) {
                int count = activeInput.read(bytes, offset, length - offset);
                if (count < 0) {
                    throw new IOException("Incomplete WebSocket frame");
                }
                offset += count;
            }
            return bytes;
        }
    }
}
