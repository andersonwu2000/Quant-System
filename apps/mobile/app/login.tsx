import { useState } from "react";
import {
  View,
  Text,
  TextInput,
  Pressable,
  StyleSheet,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { useAuth } from "../src/hooks/useAuth";

export default function LoginScreen() {
  const [serverUrl, setServerUrl] = useState("http://192.168.1.100:8000");
  const [apiKey, setApiKey] = useState("");
  const { login, loading, error } = useAuth();

  const handleLogin = () => {
    if (serverUrl && apiKey) {
      login(serverUrl, apiKey);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <View style={styles.inner}>
        <Text style={styles.title}>Quant Trading</Text>
        <Text style={styles.subtitle}>Connect to your trading server</Text>

        <Text style={styles.label}>Server URL</Text>
        <TextInput
          style={styles.input}
          value={serverUrl}
          onChangeText={setServerUrl}
          placeholder="http://192.168.1.100:8000"
          placeholderTextColor="#475569"
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
        />

        <Text style={styles.label}>API Key</Text>
        <TextInput
          style={styles.input}
          value={apiKey}
          onChangeText={setApiKey}
          placeholder="Enter your API key"
          placeholderTextColor="#475569"
          autoCapitalize="none"
          autoCorrect={false}
          secureTextEntry
        />

        {error && <Text style={styles.error}>{error}</Text>}

        <Pressable
          style={[styles.button, (!serverUrl || !apiKey) && styles.disabled]}
          onPress={handleLogin}
          disabled={loading || !serverUrl || !apiKey}
        >
          {loading ? (
            <ActivityIndicator color="#FFFFFF" />
          ) : (
            <Text style={styles.btnText}>Connect</Text>
          )}
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0F172A",
    justifyContent: "center",
  },
  inner: {
    paddingHorizontal: 32,
  },
  title: {
    color: "#F1F5F9",
    fontSize: 32,
    fontWeight: "800",
    textAlign: "center",
    marginBottom: 4,
  },
  subtitle: {
    color: "#64748B",
    fontSize: 14,
    textAlign: "center",
    marginBottom: 40,
  },
  label: {
    color: "#94A3B8",
    fontSize: 13,
    fontWeight: "600",
    marginBottom: 6,
    marginTop: 16,
  },
  input: {
    backgroundColor: "#1E293B",
    borderRadius: 10,
    padding: 14,
    color: "#F1F5F9",
    fontSize: 16,
    borderWidth: 1,
    borderColor: "#334155",
  },
  error: {
    color: "#EF4444",
    fontSize: 13,
    marginTop: 12,
    textAlign: "center",
  },
  button: {
    backgroundColor: "#3B82F6",
    borderRadius: 10,
    padding: 16,
    alignItems: "center",
    marginTop: 32,
  },
  disabled: {
    opacity: 0.5,
  },
  btnText: {
    color: "#FFFFFF",
    fontSize: 16,
    fontWeight: "700",
  },
});
