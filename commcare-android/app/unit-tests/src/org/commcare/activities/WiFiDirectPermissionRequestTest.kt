package org.commcare.activities

import android.Manifest
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.commcare.CommCareTestApplication
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config

@Config(application = CommCareTestApplication::class, sdk = [28, 31])
@RunWith(AndroidJUnit4::class)
class WiFiDirectPermissionRequestTest {
    @Test
    fun `location request includes coarse and fine on Android 12 and earlier`() {
        val activity = Robolectric.buildActivity(CommCareWiFiDirectActivity::class.java).get()
        activity.javaClass.getDeclaredMethod("requestNearbyWifiPermission").apply {
            isAccessible = true
            invoke(activity)
        }

        val request = shadowOf(activity).lastRequestedPermission
        assertArrayEquals(
            arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION),
            request.requestedPermissions,
        )
        assertEquals(2, request.requestCode)
    }
}
