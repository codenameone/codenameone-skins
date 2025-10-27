import com.codename1.impl.javase.Simulator;
import java.io.File;
import java.lang.reflect.Method;

public final class SkinHarness {
    private SkinHarness() {}

    public static void main(String[] args) throws Exception {
        if (args.length != 1) {
            System.err.println("Usage: SkinHarness <skin>");
            System.exit(64);
            return;
        }

        File skinFile = new File(args[0]).getAbsoluteFile();
        if (!skinFile.isFile()) {
            System.err.println("Skin file not found: " + skinFile);
            System.exit(66);
            return;
        }

        System.setProperty("skin", skinFile.getAbsolutePath());

        Simulator simulator = new Simulator();
        try {
            invokeIfPresent(simulator.getClass(), simulator, "init");
            invokeIfPresent(simulator.getClass(), simulator, "initialize");

            Method loadSkin = findSkinLoader(simulator.getClass());
            if (loadSkin == null) {
                System.err.println("Unable to locate loadSkin method on simulator");
                System.exit(65);
                return;
            }

            if (loadSkin.getParameterCount() == 1) {
                Class<?> paramType = loadSkin.getParameterTypes()[0];
                loadSkin.setAccessible(true);
                if (File.class.isAssignableFrom(paramType)) {
                    loadSkin.invoke(simulator, skinFile);
                } else {
                    loadSkin.invoke(simulator, skinFile.getAbsolutePath());
                }
            } else {
                System.err.println("Unsupported loadSkin signature: " + loadSkin);
                System.exit(65);
                return;
            }

            Method skinAccessor = findSkinAccessor(simulator.getClass());
            if (skinAccessor != null) {
                skinAccessor.setAccessible(true);
                Object skin = skinAccessor.invoke(simulator);
                if (skin == null) {
                    System.err.println("Simulator did not retain loaded skin instance");
                    System.exit(67);
                    return;
                }
            }

            invokeIfPresent(simulator.getClass(), simulator, "start");
            invokeIfPresent(simulator.getClass(), simulator, "stop");
            invokeIfPresent(simulator.getClass(), simulator, "startApp");
            invokeIfPresent(simulator.getClass(), simulator, "stopApp");
            invokeIfPresent(simulator.getClass(), simulator, "destroyApp");
            invokeIfPresent(simulator.getClass(), simulator, "dispose");
            invokeIfPresent(simulator.getClass(), simulator, "shutdown");
        } finally {
            // Ensure simulator resources are cleaned up even if verification fails.
            invokeIfPresent(simulator.getClass(), simulator, "destroyApp");
            invokeIfPresent(simulator.getClass(), simulator, "dispose");
            invokeIfPresent(simulator.getClass(), simulator, "shutdown");
        }
    }

    private static void invokeIfPresent(Class<?> type, Object instance, String methodName) throws Exception {
        try {
            Method method = type.getMethod(methodName);
            method.setAccessible(true);
            method.invoke(instance);
        } catch (NoSuchMethodException ignored) {
            // Method optional.
        }
    }

    private static Method findSkinLoader(Class<?> type) {
        for (Method method : type.getMethods()) {
            if (!method.getName().equals("loadSkin")) {
                continue;
            }
            if (method.getParameterCount() == 1) {
                Class<?> arg = method.getParameterTypes()[0];
                if (File.class.isAssignableFrom(arg) || CharSequence.class.isAssignableFrom(arg)) {
                    return method;
                }
            }
        }
        return null;
    }

    private static Method findSkinAccessor(Class<?> type) {
        try {
            return type.getMethod("getSkin");
        } catch (NoSuchMethodException ignored) {
            // fall through
        }
        try {
            return type.getMethod("getCurrentSkin");
        } catch (NoSuchMethodException ignored) {
            return null;
        }
    }
}
