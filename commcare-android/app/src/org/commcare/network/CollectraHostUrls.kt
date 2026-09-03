package org.commcare.network

import org.commcare.dalvik.BuildConfig
import java.net.URI

/**
 * Resolves the Collectra HQ base URL baked into the APK via
 * `COLLECTRA_HQ_BASE_URL` in local.properties.
 *
 * Safe helpers only — does not remove Dimagi fallbacks used when the base URL
 * is blank (those fallbacks keep legacy/dev installs working).
 */
object CollectraHostUrls {
    @JvmStatic
    fun getConfiguredBaseUrl(): String =
        BuildConfig.COLLECTRA_HQ_BASE_URL.trim().trimEnd('/')

    @JvmStatic
    fun isConfigured(): Boolean = getConfiguredBaseUrl().isNotEmpty()

    @JvmStatic
    fun getConfiguredHost(): String? {
        val base = getConfiguredBaseUrl()
        if (base.isEmpty()) {
            return null
        }
        return try {
            URI(base).host?.takeIf { it.isNotBlank() }
        } catch (_: Exception) {
            null
        }
    }

    /** HQ health probe used by connection diagnostics. */
    @JvmStatic
    fun getServerUpUrl(): String {
        val base = getConfiguredBaseUrl()
        return if (base.isEmpty()) {
            "https://www.commcarehq.org/serverup.txt"
        } else {
            "$base/serverup.txt"
        }
    }
}
