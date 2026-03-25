# kotlinx.serialization
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.AnnotationsKt

-keepclassmembers class kotlinx.serialization.json.** { *** Companion; }
-keepclasseswithmembers class kotlinx.serialization.json.** { kotlinx.serialization.KSerializer serializer(...); }

# Keep all @Serializable data classes (api models + any other data package)
-keep,includedescriptorclasses class com.quant.trading.data.**$$serializer { *; }
-keepclassmembers class com.quant.trading.data.** {
    *** Companion;
    *** serializer(...);
}
-keepnames class com.quant.trading.data.** { *; }

# Keep kotlinx.serialization core
-keep class kotlinx.serialization.** { *; }

# Retrofit
-keepattributes Signature, Exceptions
-keep class retrofit2.** { *; }
-keepclasseswithmembers class * { @retrofit2.http.* <methods>; }

# OkHttp
-dontwarn okhttp3.**
-dontwarn okio.**

# Hilt
-keep class dagger.hilt.** { *; }

# Google Tink / EncryptedSharedPreferences (errorprone annotations)
-dontwarn com.google.errorprone.annotations.**
-dontwarn javax.annotation.**
-dontwarn com.google.auto.value.**
-dontwarn com.google.j2objc.annotations.**
