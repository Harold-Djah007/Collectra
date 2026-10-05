package org.commcare.location

import android.Manifest
import android.content.Context
import android.content.ContextWrapper
import android.location.Location
import android.location.LocationManager
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import io.mockk.every
import io.mockk.mockk
import io.mockk.verify
import org.commcare.CommCareTestApplication
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config

@Config(application = CommCareTestApplication::class, sdk = [28])
@RunWith(AndroidJUnit4::class)
class ProviderLocationPermissionTest {
    private val manager = mockk<LocationManager>()
    private lateinit var application: CommCareTestApplication
    private lateinit var context: Context
    private val listener = RecordingListener()

    @Before
    fun setUp() {
        application = ApplicationProvider.getApplicationContext()
        context =
            object : ContextWrapper(application) {
                override fun getSystemService(name: String): Any? = if (name == LOCATION_SERVICE) manager else super.getSystemService(name)
            }
        every { manager.getProviders(true) } returns listOf(LocationManager.GPS_PROVIDER)
        every { manager.removeUpdates(any<android.location.LocationListener>()) } returns Unit
    }

    @Test
    fun `denied permission reports the failure without requesting GPS`() {
        shadowOf(application).denyPermissions(
            Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.ACCESS_COARSE_LOCATION,
        )
        val controller = CommCareProviderLocationController(context, listener)

        controller.start()

        assertEquals(1, listener.permissionFailures)
        assertEquals(0, listener.requests)
        verify(
            exactly = 0,
        ) { manager.requestLocationUpdates(any<String>(), any<Long>(), any<Float>(), any<android.location.LocationListener>()) }
    }

    @Test
    fun `permission revoked during registration can be retried`() {
        shadowOf(application).grantPermissions(
            Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.ACCESS_COARSE_LOCATION,
        )
        every { manager.requestLocationUpdates(any<String>(), any<Long>(), any<Float>(), any<android.location.LocationListener>()) } throws
            SecurityException("Permission revoked")
        val controller = CommCareProviderLocationController(context, listener)

        controller.start()
        controller.stop()
        controller.start()
        controller.stop()

        assertEquals(2, listener.permissionFailures)
        assertEquals(2, listener.requests)
    }

    private class RecordingListener : CommCareLocationListener {
        var permissionFailures = 0
        var requests = 0

        override fun onLocationRequestStart() {
            requests++
        }

        override fun missingPermissions() {
            permissionFailures++
        }

        override fun onLocationResult(result: Location) {}

        override fun onLocationRequestFailure(failure: CommCareLocationListener.Failure) {}

        override fun onLocationServiceChange(locationServiceEnabled: Boolean) {}
    }
}
