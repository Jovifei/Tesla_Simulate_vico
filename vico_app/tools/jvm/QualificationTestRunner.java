import org.junit.runner.JUnitCore;
import org.junit.runner.Result;
import org.junit.runner.notification.Failure;
import org.junit.runner.notification.RunListener;

/** JVM-only execution receipt. Assumption skips are never counted as passes. */
public final class QualificationTestRunner {
    public static void main(String[] names) throws Exception {
        if (names.length == 0) throw new IllegalArgumentException("No tests selected");
        Class<?>[] classes = new Class<?>[names.length];
        for (int i = 0; i < names.length; i++) classes[i] = Class.forName(names[i]);
        final int[] skipped = {0};
        JUnitCore junit = new JUnitCore();
        junit.addListener(new RunListener() {
            @Override public void testAssumptionFailure(Failure failure) {
                skipped[0]++;
                System.out.println("ASSUMPTION_SKIPPED " + failure.getDescription());
            }
        });
        Result result = junit.run(classes);
        for (Failure failure : result.getFailures()) {
            System.err.println(failure.getTestHeader());
            System.err.println(failure.getTrace());
        }
        System.out.printf("{\"run\":%d,\"passed\":%d,\"failed\":%d,\"assumption_skipped\":%d,\"ignored\":%d,\"runtime_ms\":%d}%n",
            result.getRunCount(), result.getRunCount() - result.getFailureCount() - skipped[0],
            result.getFailureCount(), skipped[0], result.getIgnoreCount(), result.getRunTime());
        if (!result.wasSuccessful()) System.exit(1);
    }
}
