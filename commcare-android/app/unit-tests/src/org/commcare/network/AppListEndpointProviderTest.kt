package org.commcare.network

import org.junit.Assert.assertEquals
import org.junit.Test

class AppListEndpointProviderTest {
    @Test
    fun `configured Collectra host is used for app discovery`() {
        assertEquals(
            listOf("https://collectra.example.com/phone/list_apps"),
            AppListEndpointProvider.getUrls("https://collectra.example.com"),
        )
    }

    @Test
    fun `trailing slash is removed from configured host`() {
        assertEquals(
            listOf("https://collectra.example.com/phone/list_apps"),
            AppListEndpointProvider.getUrls("https://collectra.example.com/"),
        )
    }

    @Test
    fun `complete app list endpoint is preserved`() {
        assertEquals(
            listOf("https://collectra.example.com/phone/list_apps"),
            AppListEndpointProvider.getUrls("https://collectra.example.com/phone/list_apps"),
        )
    }

    @Test
    fun `blank configuration preserves upstream endpoints`() {
        assertEquals(
            listOf(
                "https://www.commcarehq.org/phone/list_apps",
                "https://india.commcarehq.org/phone/list_apps",
            ),
            AppListEndpointProvider.getUrls(""),
        )
    }
}
