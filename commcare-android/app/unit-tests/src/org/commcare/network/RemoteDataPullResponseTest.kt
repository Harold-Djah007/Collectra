package org.commcare.network

import okhttp3.ResponseBody
import org.junit.Assert.assertSame
import org.junit.Test
import retrofit2.Response
import java.io.IOException
import java.io.InputStream

class RemoteDataPullResponseTest {
    @Test
    fun `download failure before cache creation preserves the network error`() {
        val networkError = IOException("Connection interrupted")
        val response =
            object : RemoteDataPullResponse(null, Response.success<ResponseBody>(null)) {
                override fun getInputStream(): InputStream = throw networkError
            }

        try {
            response.writeResponseToCache(null)
            throw AssertionError("Expected the network error")
        } catch (error: IOException) {
            assertSame(networkError, error)
        }
    }
}
