package org.commcare.activities

import android.view.View
import androidx.core.view.GravityCompat
import androidx.drawerlayout.widget.DrawerLayout
import org.commcare.dalvik.R
import org.commcare.navdrawer.BaseDrawerController.NavItemType
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.robolectric.shadows.ShadowLooper
import org.robolectric.shadows.ShadowSystemClock
import java.time.Duration

/**
 * Characterization pins for the nav drawer's traditional destination (app switching).
 *
 *
 * The Connect/PersonalId destinations live in [HomeConnectDrawerNavigationTest].
 */
class HomeDrawerNavigationTest : BaseHomeScreenActivityTest() {
    @Test
    fun `account navigation opens the drawer without logging out`() {
        val home = buildVisibleHome()
        home.findViewById<View>(R.id.collectra_nav_account).performClick()
        val drawer = home.findViewById<DrawerLayout>(R.id.drawer_layout)
        ShadowSystemClock.advanceBy(Duration.ofSeconds(1))
        drawer.computeScroll()
        ShadowLooper.idleMainLooper()
        assertTrue(drawer.isDrawerOpen(GravityCompat.START))
        assertFalse(home.isFinishing)
    }
    // ---- COMMCARE_APPS: app switching ----

    @Test
    fun `commcare apps raises the switch-app confirmation`() {
        val home = buildVisibleHome()
        home.handleDrawerItemClick(NavItemType.COMMCARE_APPS)
        home.supportFragmentManager.executePendingTransactions()

        assertNotNull("selecting apps should prompt before leaving home", home.currentAlertDialog)
    }

    @Test
    fun `commcare apps does not leave home until the prompt is confirmed`() {
        val home = buildVisibleHome()
        home.handleDrawerItemClick(NavItemType.COMMCARE_APPS)
        home.supportFragmentManager.executePendingTransactions()

        assertFalse("home should stay up while the prompt is unanswered", home.isFinishing)
    }
}
