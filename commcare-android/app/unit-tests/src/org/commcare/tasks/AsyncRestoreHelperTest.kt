package org.commcare.tasks

import org.commcare.core.network.bitcache.BitCache
import org.commcare.network.RemoteDataPullResponse
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.mockito.Mockito.mock
import org.mockito.Mockito.`when`
import java.io.ByteArrayInputStream

class AsyncRestoreHelperTest {
    @Test
    fun `invalid retry delays return bad data without crashing`() {
        for (header in listOf(null, "", "invalid", "0", "-1", Long.MAX_VALUE.toString())) {
            val response = mock(RemoteDataPullResponse::class.java)
            `when`(response.retryHeader).thenReturn(header)
            val helper = AsyncRestoreHelper(null)

            assertEquals(DataPullTask.PullTaskResult.BAD_DATA, helper.handleRetryResponseCode(response).data)
            assertEquals(-1L, helper.retryAtTime)
        }
    }

    @Test
    fun `long retry delays retain their full duration`() {
        val helper = AsyncRestoreHelper(mock(DataPullTask::class.java))
        val before = System.currentTimeMillis()
        assertEquals(
            DataPullTask.PullTaskResult.RETRY_NEEDED,
            helper.handleRetryResponseCode(response("2147483647", "55", "100")).data,
        )
        assertTrue(helper.retryAtTime >= before + 2147483647000L)
        assertEquals(55, helper.serverProgressCompletedSoFar)
    }

    @Test
    fun `malformed progress returns bad data`() {
        val helper = AsyncRestoreHelper(mock(DataPullTask::class.java))
        assertEquals(
            DataPullTask.PullTaskResult.BAD_DATA,
            helper.handleRetryResponseCode(response("1", "invalid", "100")).data,
        )
        assertEquals(-1L, helper.retryAtTime)
    }

    private fun response(
        header: String,
        done: String,
        total: String,
    ): RemoteDataPullResponse {
        val response = mock(RemoteDataPullResponse::class.java)
        val cache = mock(BitCache::class.java)
        `when`(response.retryHeader).thenReturn(header)
        `when`(response.writeResponseToCache(null)).thenReturn(cache)
        `when`(cache.retrieveCache()).thenReturn(
            ByteArrayInputStream(
                "<restore><progress done=\"$done\" total=\"$total\"/></restore>".toByteArray(),
            ),
        )
        return response
    }
}
