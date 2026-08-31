package org.commcare.network

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CollectraHostConfigTest {
    @Test
    fun `normalize strips trailing slash`() {
        assertEquals(
            "http://192.168.1.195:8000",
            CollectraHostConfig.normalizeBaseUrl("http://192.168.1.195:8000/"),
        )
    }

    @Test
    fun `sms allowlist accepts collectra host and private lan`() {
        assertTrue(CollectraHostConfig.isAllowedSmsInstallHost("www.commcarehq.org"))
        assertTrue(CollectraHostConfig.isAllowedSmsInstallHost("192.168.1.195"))
        assertTrue(CollectraHostConfig.isAllowedSmsInstallHost("localhost"))
        assertFalse(CollectraHostConfig.isAllowedSmsInstallHost("evil.example.com"))
    }

    @Test
    fun `fallback urls use configured collectra host`() {
        assertEquals(
            "http://192.168.1.195:8000/receiver/submit/pf",
            CollectraHostConfig.normalizeBaseUrl("http://192.168.1.195:8000") + "/receiver/submit/pf",
        )
    }
}
