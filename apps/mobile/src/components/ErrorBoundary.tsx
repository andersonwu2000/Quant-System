import { Component } from "react";
import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import type { ReactNode, ErrorInfo } from "react";

interface Props { children: ReactNode; }
interface State { hasError: boolean; error: Error | null; }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };
  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary:", error, info.componentStack);
  }
  render() {
    if (this.state.hasError) {
      return (
        <View style={styles.container}>
          <Text style={styles.icon}>!</Text>
          <Text style={styles.title}>Something went wrong</Text>
          <Text style={styles.message}>{this.state.error?.message}</Text>
          <TouchableOpacity style={styles.button}
            onPress={() => this.setState({ hasError: false, error: null })}>
            <Text style={styles.buttonText}>Try Again</Text>
          </TouchableOpacity>
        </View>
      );
    }
    return this.props.children;
  }
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0F172A", justifyContent: "center", alignItems: "center", padding: 24 },
  icon: { fontSize: 48, color: "#F59E0B", fontWeight: "800", marginBottom: 16 },
  title: { color: "#F1F5F9", fontSize: 20, fontWeight: "700", marginBottom: 8 },
  message: { color: "#94A3B8", fontSize: 14, textAlign: "center", marginBottom: 24 },
  button: { backgroundColor: "#2563EB", borderRadius: 10, paddingHorizontal: 24, paddingVertical: 12 },
  buttonText: { color: "#FFF", fontWeight: "600", fontSize: 15 },
});
