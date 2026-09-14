package org.commcare.network

import org.commcare.dalvik.BuildConfig

object AppInstallCodeResolver {
    private const val BITLY_PREFIX = "http://bit.ly/"
    private const val INSTALL_CODE_PATH = "/s/"

    @JvmStatic
    @JvmOverloads
    fun resolve(code: String, configuredBaseUrl: String = BuildConfig.COLLECTRA_HQ_BASE_URL): String {
        val trimmed = code.trim()
        if (trimmed.contains("://")) {
            return trimmed
        }
        val normalized = configuredBaseUrl.trim().trimEnd('/')
        return if (normalized.isEmpty()) {
            BITLY_PREFIX + trimmed
        } else {
            normalized + INSTALL_CODE_PATH + trimmed
        }
    }
}
