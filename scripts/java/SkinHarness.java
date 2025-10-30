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
        int parameterCount = loadSkin.getParameterCount();
        Class<?>[] paramTypes = loadSkin.getParameterTypes();
        Object firstArg;
        if (File.class.isAssignableFrom(paramTypes[0])) {
            firstArg = skinFile;
        } else {
            firstArg = skinFile.getAbsolutePath();
        }

        loadSkin.setAccessible(true);

        if (parameterCount == 1) {
            loadSkin.invoke(simulator, firstArg);
            return;
        }

        if (parameterCount == 2 && isBooleanType(paramTypes[1])) {
            Object secondArg = paramTypes[1].isPrimitive() ? false : Boolean.FALSE;
            loadSkin.invoke(simulator, firstArg, secondArg);
            return;
        }

        System.err.println("Unsupported loadSkin signature: " + loadSkin);
        System.exit(65);
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
        if (count == 1) {
            Class<?> arg = method.getParameterTypes()[0];
            return File.class.isAssignableFrom(arg) || CharSequence.class.isAssignableFrom(arg);
        }

        if (count == 2) {
            Class<?>[] params = method.getParameterTypes();
            boolean firstValid = File.class.isAssignableFrom(params[0]) || CharSequence.class.isAssignableFrom(params[0]);
            boolean secondValid = isBooleanType(params[1]);
            return firstValid && secondValid;
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
