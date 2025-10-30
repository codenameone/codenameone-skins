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

            invokeSkinLoader(loadSkin, simulator, skinFile);

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

    private static void invokeSkinLoader(Method loadSkin, Simulator simulator, File skinFile) throws Exception {
        Class<?>[] paramTypes = loadSkin.getParameterTypes();
        Object[] args = new Object[paramTypes.length];

        if (File.class.isAssignableFrom(paramTypes[0])) {
            args[0] = skinFile;
        } else {
            args[0] = skinFile.getAbsolutePath();
        }

        for (int i = 1; i < paramTypes.length; i++) {
            Class<?> type = paramTypes[i];
            if (!isBooleanType(type)) {
                System.err.println("Unsupported loadSkin parameter type at index " + i + ": " + type.getName());
                System.exit(65);
                return;
            }
            args[i] = type.isPrimitive() ? false : Boolean.FALSE;
        }

        loadSkin.setAccessible(true);
        loadSkin.invoke(simulator, args);
    }

    private static Method findSkinLoader(Class<?> type) {
        Method method = findSkinLoaderInHierarchy(type);
        if (method != null) {
            return method;
        }
        for (Method candidate : type.getMethods()) {
            if (isSkinLoader(candidate)) {
                return candidate;
            }
        }
        return null;
    }

    private static Method findSkinLoaderInHierarchy(Class<?> type) {
        Class<?> current = type;
        while (current != null) {
            for (Method candidate : current.getDeclaredMethods()) {
                if (isSkinLoader(candidate)) {
                    candidate.setAccessible(true);
                    return candidate;
                }
            }
            current = current.getSuperclass();
        }
        return null;
    }

    private static boolean isSkinLoader(Method method) {
        String name = method.getName();
        if (!name.equals("loadSkin") && !name.equals("loadSkinFromFile")) {
            return false;
        }

        int count = method.getParameterCount();
        if (count >= 1) {
            Class<?>[] params = method.getParameterTypes();
            boolean firstValid = File.class.isAssignableFrom(params[0]) || CharSequence.class.isAssignableFrom(params[0]);
            if (!firstValid) {
                return false;
            }
            for (int i = 1; i < count; i++) {
                if (!isBooleanType(params[i])) {
                    return false;
                }
            }
            return true;
        }

        return false;
    }

    private static boolean isBooleanType(Class<?> type) {
        return type == boolean.class || type == Boolean.class;
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
