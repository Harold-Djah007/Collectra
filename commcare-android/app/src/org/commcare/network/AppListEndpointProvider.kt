package org.commcare.network

import org.commcare.dalvik.BuildConfig

object AppListEndpointProvider {
    private const val APP_LIST_PATH = "/phone/list_apps"

    @JvmStatic
    fun getUrls(): List<String> = getUrls(BuildConfig.COLLECTRA_HQ_BASE_URL)

    internal fun getUrls(configuredBaseUrl: String): List<String> {
        val normalizedUrl = configuredBaseUrl.trim().trimEnd('/')
        if (normalizedUrl.isEmpty()) {
            // Collectra builds must set COLLECTRA_HQ_BASE_URL; do not fall back to Dimagi HQ.
            return emptyList()
        }

        return listOf(
            if (normalizedUrl.endsWith(APP_LIST_PATH)) {
                normalizedUrl
            } else {
                "$normalizedUrl$APP_LIST_PATH"
            },
        )
    }
}
