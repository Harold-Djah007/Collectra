package org.commcare.network

import org.commcare.dalvik.BuildConfig

object AppListEndpointProvider {
    private const val COMMCARE_PRODUCTION_URL = "https://www.commcarehq.org/phone/list_apps"
    private const val COMMCARE_INDIA_URL = "https://india.commcarehq.org/phone/list_apps"
    private const val APP_LIST_PATH = "/phone/list_apps"

    @JvmStatic
    fun getUrls(): List<String> = getUrls(BuildConfig.COLLECTRA_HQ_BASE_URL)

    internal fun getUrls(configuredBaseUrl: String): List<String> {
        val normalizedUrl = configuredBaseUrl.trim().trimEnd('/')
        if (normalizedUrl.isEmpty()) {
            return listOf(COMMCARE_PRODUCTION_URL, COMMCARE_INDIA_URL)
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
