package org.commcare.utils

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkInfo
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.mockito.kotlin.mock
import org.mockito.kotlin.whenever

class ConnectivityStatusTest {
    @Test
    fun `connected wifi is available`() {
        assertTrue(
            ConnectivityStatus.isNetworkAvailable(
                contextWithNetwork(ConnectivityManager.TYPE_WIFI, true),
            ),
        )
    }

    @Test
    fun `connected mobile data is available`() {
        assertTrue(
            ConnectivityStatus.isNetworkAvailable(
                contextWithNetwork(ConnectivityManager.TYPE_MOBILE, true),
            ),
        )
    }

    @Test
    fun `disconnected network is unavailable`() {
        assertFalse(
            ConnectivityStatus.isNetworkAvailable(
                contextWithNetwork(ConnectivityManager.TYPE_MOBILE, false),
            ),
        )
    }

    private fun contextWithNetwork(networkType: Int, connected: Boolean): Context {
        val context = mock<Context>()
        val connectivityManager = mock<ConnectivityManager>()
        val networkInfo = mock<NetworkInfo>()

        whenever(context.getSystemService(Context.CONNECTIVITY_SERVICE)).thenReturn(connectivityManager)
        whenever(connectivityManager.activeNetworkInfo).thenReturn(networkInfo)
        whenever(networkInfo.type).thenReturn(networkType)
        whenever(networkInfo.isConnected).thenReturn(connected)

        return context
    }
}
