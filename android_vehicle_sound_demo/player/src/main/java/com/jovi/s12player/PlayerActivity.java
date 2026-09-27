package com.jovi.s12player;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.os.Handler;
import android.os.IBinder;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.SeekBar;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import java.io.BufferedReader;
import java.io.InputStreamReader;

public final class PlayerActivity extends Activity {
    private static final int LOCATION_REQUEST = 12;
    private final Handler main = new Handler();
    private DriveAudioService service;
    private boolean bound;
    private Spinner profiles;
    private Spinner axes;
    private SeekBar volume;
    private TextView status;
    private TextView speed;
    private TextView quality;
    private TextView diagnostics;
    private final ServiceConnection connection = new ServiceConnection() {
        @Override public void onServiceConnected(ComponentName name, IBinder binder) {
            service = ((DriveAudioService.LocalBinder) binder).service();
        }
        @Override public void onServiceDisconnected(ComponentName name) { service = null; }
    };
    private final Runnable refresh = new Runnable() {
        @Override public void run() {
            if (service != null) {
                status.setText(service.status());
                double liveSpeed = service.speedKmh();
                speed.setText(Double.isFinite(liveSpeed)
                        ? getString(R.string.speed_readout, liveSpeed)
                        : getString(R.string.speed_unavailable));
                quality.setText(service.quality());
                diagnostics.setText(service.diagnostics());
            }
            main.postDelayed(this, 500);
        }
    };

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        buildUi();
        bound = bindService(new Intent(this, DriveAudioService.class), connection,
                Context.BIND_AUTO_CREATE);
        main.post(refresh);
    }

    private void buildUi() {
        ScrollView scroll = new ScrollView(this);
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(32, 28, 32, 32);
        scroll.addView(content);
        TextView title = new TextView(this);
        title.setText(R.string.player_title);
        title.setTextSize(24);
        content.addView(title);
        TextView boundary = new TextView(this);
        boundary.setText(R.string.experimental_boundary);
        content.addView(boundary);

        profiles = spinner(content, new String[]{getString(R.string.profile_v8),
                getString(R.string.profile_rotary)},
                getPreferences(MODE_PRIVATE).getInt("profile", 0));
        profiles.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener() {
            @Override public void onItemSelected(android.widget.AdapterView<?> parent,
                    android.view.View view, int position, long id) {
                getPreferences(MODE_PRIVATE).edit().putInt("profile", position).apply();
                if (service != null) service.selectProfile(position);
            }
            @Override public void onNothingSelected(android.widget.AdapterView<?> parent) {}
        });
        label(content, R.string.volume_label, 16);
        volume = new SeekBar(this);
        volume.setMax(100);
        volume.setProgress(getPreferences(MODE_PRIVATE).getInt("volume", 75));
        volume.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override public void onProgressChanged(SeekBar bar, int value, boolean fromUser) {
                if (!fromUser) return;
                getPreferences(MODE_PRIVATE).edit().putInt("volume", value).apply();
                if (service != null) service.setVolume(value / 100.0f);
            }
            @Override public void onStartTrackingTouch(SeekBar bar) {}
            @Override public void onStopTrackingTouch(SeekBar bar) {}
        });
        content.addView(volume);
        TextView mounting = new TextView(this);
        mounting.setText(R.string.mounting_instruction);
        content.addView(mounting);
        axes = spinner(content, new String[]{getString(R.string.axis_plus_x),
                getString(R.string.axis_plus_y), getString(R.string.axis_minus_x),
                getString(R.string.axis_minus_y)},
                getPreferences(MODE_PRIVATE).getInt("axis", 0));
        axes.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener() {
            @Override public void onItemSelected(android.widget.AdapterView<?> parent,
                    android.view.View view, int position, long id) {
                getPreferences(MODE_PRIVATE).edit().putInt("axis", position).apply();
            }
            @Override public void onNothingSelected(android.widget.AdapterView<?> parent) {}
        });

        addButton(content, R.string.button_start_replay, () -> start(DriveAudioService.REPLAY));
        addButton(content, R.string.button_sensors, this::requestDrive);
        addButton(content, R.string.button_stop, () -> {
            if (service != null) service.stop();
        });
        status = label(content, R.string.status_stopped_initial, 18);
        speed = label(content, R.string.speed_initial, 30);
        quality = label(content, R.string.quality_start_hint, 14);
        diagnostics = label(content, R.string.audio_waiting, 13);
        addButton(content, R.string.button_licenses, this::showLicenses);
        addButton(content, R.string.button_share_diagnostics, this::shareDiagnostics);
        setContentView(scroll);
    }

    private Spinner spinner(LinearLayout parent, String[] values, int selected) {
        Spinner spinner = new Spinner(this);
        ArrayAdapter<String> adapter = new ArrayAdapter<>(this,
                android.R.layout.simple_spinner_dropdown_item, values);
        spinner.setAdapter(adapter);
        spinner.setSelection(Math.max(0, Math.min(values.length - 1, selected)));
        parent.addView(spinner);
        return spinner;
    }

    private TextView label(LinearLayout parent, int stringId, int size) {
        TextView view = new TextView(this);
        view.setText(stringId);
        view.setTextSize(size);
        parent.addView(view);
        return view;
    }

    private void addButton(LinearLayout parent, int stringId, Runnable action) {
        Button button = new Button(this);
        button.setText(stringId);
        button.setOnClickListener(view -> action.run());
        parent.addView(button);
    }

    private void requestDrive() {
        if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)
                != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.ACCESS_FINE_LOCATION}, LOCATION_REQUEST);
            return;
        }
        start(DriveAudioService.DRIVE);
    }

    private void start(String mode) {
        Intent intent = new Intent(this, DriveAudioService.class).setAction(mode)
                .putExtra(DriveAudioService.PROFILE, profiles.getSelectedItemPosition())
                .putExtra(DriveAudioService.AXIS, axes.getSelectedItemPosition())
                .putExtra(DriveAudioService.VOLUME, volume.getProgress() / 100.0f);
        try { startForegroundService(intent); }
        catch (RuntimeException error) {
            status.setText(getString(R.string.status_service_failed,
                    error.getClass().getSimpleName()));
        }
    }

    @Override public void onRequestPermissionsResult(int requestCode, String[] permissions,
            int[] results) {
        super.onRequestPermissionsResult(requestCode, permissions, results);
        if (requestCode == LOCATION_REQUEST && results.length > 0
                && results[0] == PackageManager.PERMISSION_GRANTED) start(DriveAudioService.DRIVE);
        else if (requestCode == LOCATION_REQUEST) status.setText(R.string.status_permission_denied);
    }

    private void shareDiagnostics() {
        Intent send = new Intent(Intent.ACTION_SEND);
        send.setType("text/plain");
        send.putExtra(Intent.EXTRA_TEXT, getString(R.string.share_report,
                profiles.getSelectedItem(), status.getText(), quality.getText(), diagnostics.getText()));
        startActivity(Intent.createChooser(send, getString(R.string.share_chooser)));
    }

    private void showLicenses() {
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(
                getAssets().open("third_party_licenses/oboe-1.11.0-LICENSE.txt")))) {
            StringBuilder text = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) text.append(line).append('\n');
            new AlertDialog.Builder(this).setTitle(R.string.license_title)
                    .setMessage(text.toString()).setPositiveButton("Close", null).show();
        } catch (Exception error) {
            Toast.makeText(this, R.string.license_unavailable, Toast.LENGTH_SHORT).show();
        }
    }

    @Override protected void onDestroy() {
        main.removeCallbacks(refresh);
        if (bound) unbindService(connection);
        super.onDestroy();
    }
}
