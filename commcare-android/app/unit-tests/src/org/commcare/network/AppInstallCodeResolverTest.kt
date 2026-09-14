package org.commcare.network

import org.junit.Assert.assertEquals
import org.junit.Test

class AppInstallCodeResolverTest {
    @Test
    fun `collectra host prefixes an app code`() {
        assertEquals(
            "https://collectra.example.com/s/abc2345",
            AppInstallCodeResolver.resolve("abc2345", "https://collectra.example.com"),
        )
    }

    @Test
    fun `trailing slash is removed from configured host`() {
        assertEquals(
            "https://collectra.example.com/s/abc2345",
            AppInstallCodeResolver.resolve("abc2345", "https://collectra.example.com/"),
        )
    }

    @Test
    fun `full urls are left unchanged`() {
        assertEquals(
            "https://collectra.example.com/s/abc2345",
            AppInstallCodeResolver.resolve(
                "https://collectra.example.com/s/abc2345",
                "https://other.example.com",
            ),
        )
    }

    @Test
    fun `blank configuration keeps bitly codes`() {
        assertEquals(
            "http://bit.ly/abc2345",
            AppInstallCodeResolver.resolve("abc2345", ""),
        )
    }
}
