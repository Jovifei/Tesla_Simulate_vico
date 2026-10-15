package com.vico.simulator.sound;

import java.lang.reflect.Field;
import java.lang.reflect.Proxy;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import org.junit.Test;
import static org.junit.Assert.*;

/** Exercises the real method without Android hardware; no assets are loaded. */
public class AudioEngineOwnershipTest {
    private static Object allocate(Class<?> type) throws Exception {
        Class<?> allocatorType = Class.forName("sun.misc.Unsafe");
        Field field = allocatorType.getDeclaredField("theUnsafe");
        field.setAccessible(true);
        return allocatorType.getMethod("allocateInstance", Class.class).invoke(field.get(null), type);
    }

    private static void set(Object owner, String name, Object value) throws Exception {
        Field field = owner.getClass().getDeclaredField(name);
        field.setAccessible(true);
        field.set(owner, value);
    }

    private static Map<String, Object> fields(Object owner) throws Exception {
        Map<String, Object> values = new LinkedHashMap<>();
        for (Field field : owner.getClass().getDeclaredFields()) {
            if (java.lang.reflect.Modifier.isStatic(field.getModifiers())) continue;
            field.setAccessible(true);
            values.put(field.getName(), field.get(owner));
        }
        return values;
    }

    private void busySelectionPreservesEverything(boolean running, boolean writerAlive) throws Exception {
        Class<?> engineType = Class.forName("com.vico.simulator.sound.AudioEngine");
        Object engine = allocate(engineType);
        Object model = allocate(Class.forName("com.vico.simulator.sound.MatlabV6SoundBankEngine"));
        set(model, "cache", new HashMap<>());
        set(model, "normalCache", new HashMap<>());
        Object route = Class.forName("com.vico.simulator.sound.C63QualificationRoute").getDeclaredConstructor().newInstance();
        Class<?> providerType = Class.forName("com.vico.simulator.sound.C63QualificationPcmProvider");
        Object provider = Proxy.newProxyInstance(providerType.getClassLoader(), new Class<?>[]{providerType},
            (proxy, method, args) -> { throw new AssertionError("Busy selection must not touch the qualification provider"); });
        set(route, "provider", provider);
        set(engine, "model", model);
        set(engine, "qualificationRoute", route);
        set(engine, "running", running);
        set(engine, "current", allocate(Class.forName("com.vico.simulator.sound.SoundState")));
        set(engine, "sampleRate", 96000);
        CountDownLatch entered = new CountDownLatch(1), exit = new CountDownLatch(1);
        Thread writer = new Thread(() -> {
            entered.countDown();
            try { exit.await(); } catch (InterruptedException error) { Thread.currentThread().interrupt(); }
        });
        if (writerAlive) { writer.start(); entered.await(); set(engine, "thread", writer); }
        try {
            Map<String, Object> beforeEngine = fields(engine), beforeModel = fields(model), beforeRoute = fields(route);
            assertFalse((Boolean) engineType.getMethod("setVehicle", String.class).invoke(engine, "missing-test-bank"));
            assertEquals("Busy selection must not mutate engine publication", beforeEngine, fields(engine));
            assertEquals("Busy selection must not mutate model", beforeModel, fields(model));
            assertSame("Busy selection must not clear qualification route", beforeRoute.get("provider"), fields(route).get("provider"));
        } finally { exit.countDown(); if (writerAlive) writer.join(); }
    }

    @Test public void runningOwnerRejectsWithoutMutation() throws Exception { busySelectionPreservesEverything(true, true); }
    @Test public void fadingWriterRejectsWithoutMutation() throws Exception { busySelectionPreservesEverything(false, true); }
    @Test public void runningFlagAloneRejectsWithoutMutation() throws Exception { busySelectionPreservesEverything(true, false); }

    @Test public void authoritativeBusyQueryCoversIdleRunningAndFading() throws Exception {
        Class<?> type = Class.forName("com.vico.simulator.sound.AudioEngine");
        java.lang.reflect.Method query = java.util.Arrays.stream(type.getMethods())
            .filter(method -> method.getName().equals("isPlaybackBusy")).findFirst().orElse(null);
        assertNotNull("UI and preparation must share the engine's authoritative busy query", query);
        Object engine = allocate(type);
        assertFalse((Boolean) query.invoke(engine));
        set(engine, "running", true);
        assertTrue((Boolean) query.invoke(engine));
        set(engine, "running", false);
        CountDownLatch exit = new CountDownLatch(1), entered = new CountDownLatch(1);
        Thread writer = new Thread(() -> {
            entered.countDown();
            try { exit.await(); } catch (InterruptedException error) { Thread.currentThread().interrupt(); }
        });
        writer.start(); entered.await(); set(engine, "thread", writer);
        try { assertTrue((Boolean) query.invoke(engine)); }
        finally { exit.countDown(); writer.join(); }
        assertFalse((Boolean) query.invoke(engine));
    }

    private void actualStartTrackFailure(boolean withCapture) throws Exception {
        Class<?> type = Class.forName("com.vico.simulator.sound.AudioEngine");
        Object engine = allocate(type);
        Object model = allocate(Class.forName("com.vico.simulator.sound.MatlabV6SoundBankEngine"));
        // This fixture bypasses missing assets; it does not enable a device prototype.
        set(model, "prototypeEnabled", true);
        set(engine, "model", model);
        set(engine, "sampleRate", 48000);
        Object capture = withCapture ? allocate(Class.forName("com.vico.simulator.sound.BoundedPcmCapture")) : null;
        set(engine, "digitalCapture", capture);
        Object started;
        try { started = type.getMethod("start").invoke(engine); }
        catch (java.lang.reflect.InvocationTargetException error) {
            throw new AssertionError("Actual start escaped its Boolean failure contract", error.getCause());
        }
        assertFalse("Actual start must report ordinary AudioTrack initialization exceptions as false",
            (Boolean) started);
        Map<String, Object> state = fields(engine);
        assertFalse((Boolean) state.get("running"));
        assertNull(state.get("thread"));
        assertNull(state.get("track"));
        String error = (String) state.get("lastAudioError");
        assertNotNull("Actual start must retain initialization failure diagnostics", error);
        assertTrue(error, error.startsWith("AudioTrack creation failed:"));
        if (capture != null) {
            assertTrue("Failed initialization must mark capture failed", (Boolean) fields(capture).get("failed"));
            assertTrue("Failed initialization must finish capture", (Boolean) fields(capture).get("isFinished"));
        }
        // Installed Android SDK stubs throw here; no real output device is accessed.
    }

    @Test public void actualStartReportsTrackInitializationExceptionAsBooleanFailure() throws Exception {
        actualStartTrackFailure(false);
    }

    @Test public void actualStartTrackExceptionFailsAndFinishesArmedCapture() throws Exception {
        actualStartTrackFailure(true);
    }
}
