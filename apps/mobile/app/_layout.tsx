import { useEffect, useState } from "react";
import { ActivityIndicator, View } from "react-native";
import { Stack, useRouter, useSegments } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider } from "react-native-safe-area-context";
import * as SecureStore from "expo-secure-store";
import { AuthProvider, useAuth } from "../src/hooks/useAuth";
import { ErrorBoundary } from "../src/components/ErrorBoundary";
import { I18nContext, translations, type Lang } from "../src/i18n";

function RootNavigator() {
  const { authenticated, loading } = useAuth();
  const router = useRouter();
  const segments = useSegments();

  // Redirect based on auth state (C2: proper Expo Router pattern)
  useEffect(() => {
    if (loading) return;

    const inAuthScreen = segments[0] === "login";

    if (!authenticated && !inAuthScreen) {
      router.replace("/login");
    } else if (authenticated && inAuthScreen) {
      router.replace("/(tabs)");
    }
  }, [authenticated, loading, segments, router]);

  if (loading) {
    return (
      <View style={{ flex: 1, backgroundColor: "#0F172A", justifyContent: "center", alignItems: "center" }}>
        <StatusBar style="light" />
        <ActivityIndicator size="large" color="#3B82F6" />
      </View>
    );
  }

  return (
    <>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: "#0F172A" },
          headerTintColor: "#F1F5F9",
          contentStyle: { backgroundColor: "#0F172A" },
        }}
      >
        <Stack.Screen name="login" options={{ headerShown: false }} />
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      </Stack>
    </>
  );
}

const LANG_KEY = "quant_lang";

export default function RootLayout() {
  const [lang, setLangState] = useState<Lang>("en");

  useEffect(() => {
    SecureStore.getItemAsync(LANG_KEY).then((saved) => {
      if (saved === "zh" || saved === "en") {
        setLangState(saved);
      }
    });
  }, []);

  const setLang = (newLang: Lang) => {
    setLangState(newLang);
    SecureStore.setItemAsync(LANG_KEY, newLang);
  };

  return (
    <ErrorBoundary>
      <I18nContext.Provider value={{ t: translations[lang], lang, setLang }}>
        <SafeAreaProvider>
          <AuthProvider>
            <RootNavigator />
          </AuthProvider>
        </SafeAreaProvider>
      </I18nContext.Provider>
    </ErrorBoundary>
  );
}
