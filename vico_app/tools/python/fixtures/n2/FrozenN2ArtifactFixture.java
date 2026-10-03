import java.io.DataOutputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;

/** Test-only frozen wire-format fixture. No renderer, references, scoring or calibration. */
class FrozenN2ArtifactFixture {
    private static double sum(double[] values) {
        double sum = 0;
        for (double value : values) sum += value;
        return sum;
    }

    private static double[] response(int size, double hz, double tau, double phase) {
        double[] values = new double[size];
        for (int i = 0; i < size; i++) {
            values[i] = Math.exp(-i / (tau * 48000)) * Math.sin(2.0 * Math.PI * hz * i / 48000 + phase);
        }
        double mean = sum(values) / size;
        for (int i = 0; i < size; i++) values[i] -= mean;
        values[size - 1] -= sum(values);
        double energy = 0;
        for (double value : values) energy += value * value;
        double norm = Math.sqrt(energy);
        for (int i = 0; i < size; i++) values[i] /= norm;
        return values;
    }

    private static String identity(double[][] arrays, double[] scalars, long[] seeds) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        digest.update("C63_N2_CONTINUOUS_V1".getBytes("US-ASCII"));
        ByteBuffer bytes = ByteBuffer.allocate(1_000_000).order(ByteOrder.LITTLE_ENDIAN);
        for (int value : new int[]{48000, 8, 4096, 12288, 48, 24}) bytes.putInt(value);
        for (double value : scalars) bytes.putDouble(value);
        for (long value : seeds) bytes.putLong(value);
        for (double[] values : arrays) for (double value : values) bytes.putDouble(value);
        digest.update(bytes.array(), 0, bytes.position());
        return HexFormat.of().formatHex(digest.digest());
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 1) throw new IllegalArgumentException("new fixture output path required");
        Path output = Path.of(args[0]);
        if (Files.exists(output)) throw new IllegalArgumentException("fixture output already exists");
        double[] edges = {80, 140, 220, 340, 520, 800, 1250, 2000, 3200};
        double[][] arrays = new double[12][];
        arrays[0] = new double[]{.52, .46, .39, .33, .27, .22, .17, .12};
        for (int i = 0; i < 8; i++) {
            arrays[i + 1] = response(4096, Math.sqrt(edges[i] * edges[i + 1]), .038 - i * .003, i * .17);
        }
        arrays[9] = response(12288, 95, .055, .11);
        arrays[10] = response(12288, 430, .045, .37);
        arrays[11] = response(12288, 1250, .030, .73);
        long[] seeds = {0x4e325f535243L, 5900017L, 0x4e325f525350L};
        String unit = identity(arrays, new double[]{1, .08, 1, .20}, seeds);
        if (!unit.equals("98dec5a954e836a0105241a04e920b8209f239441a51d039a46eb6b4f8e287c0")) {
            throw new IllegalStateException("fixture differs from frozen calibration profile: " + unit);
        }
        double[] scalars = {13.728409855272066, .08, 18.2039020043, .20};
        String profile = identity(arrays, scalars, seeds);
        try (DataOutputStream stream = new DataOutputStream(Files.newOutputStream(output))) {
            for (int value : new int[]{0x4e324250, 2, 8, 4096, 12288}) stream.writeInt(value);
            stream.writeUTF(profile);
            for (double value : scalars) stream.writeDouble(value);
            for (long value : seeds) stream.writeLong(value);
            for (double[] values : arrays) {
                stream.writeInt(values.length);
                for (double value : values) stream.writeDouble(value);
            }
        }
        System.out.println(profile);
    }
}
