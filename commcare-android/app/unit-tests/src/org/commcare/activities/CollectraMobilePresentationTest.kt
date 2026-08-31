package org.commcare.activities

import android.view.ContextThemeWrapper
import android.view.LayoutInflater
import android.view.View
import android.widget.TextView
import androidx.cardview.widget.CardView
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.commcare.CommCareTestApplication
import org.commcare.dalvik.R
import org.javarosa.core.services.locale.Localization
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config

@Config(application = CommCareTestApplication::class)
@RunWith(AndroidJUnit4::class)
class CollectraMobilePresentationTest {
    private val inflater: LayoutInflater =
        LayoutInflater.from(
            ContextThemeWrapper(
                ApplicationProvider.getApplicationContext(),
                R.style.CommonTheme,
            ),
        )

    @Test
    fun `login presents Collectra identity and offline guidance`() {
        val view = inflater.inflate(R.layout.screen_login, null)

        assertEquals(View.VISIBLE, view.findViewById<View>(R.id.collectra_login_title).visibility)
        assertEquals(View.VISIBLE, view.findViewById<View>(R.id.collectra_offline_ready).visibility)
        assertNotNull(view.findViewById<View>(R.id.collectra_login_panel).background)
    }

    @Test
    fun `setup presents Collectra workspace choices`() {
        val view = inflater.inflate(R.layout.select_install_mode_fragment, null)

        assertEquals(View.VISIBLE, view.findViewById<View>(R.id.collectra_install_title).visibility)
        assertEquals(View.VISIBLE, view.findViewById<View>(R.id.btn_fetch_uri).visibility)
        assertEquals(View.VISIBLE, view.findViewById<View>(R.id.enter_app_location).visibility)
    }

    @Test
    fun `home card uses a defined surface`() {
        val view = inflater.inflate(R.layout.square_card, null)
        val card = view.findViewById<CardView>(R.id.home_card)

        assertNotNull(card.background)
        assertTrue(card.radius > 0)
        assertNotNull(view.findViewById<View>(R.id.card_accent))
    }

    @Test
    fun `workspace header and navigation use Collectra structure`() {
        val header = inflater.inflate(R.layout.grid_header_top_banner, null)
        val navigation = inflater.inflate(R.layout.nav_drawer_base, null)

        assertEquals(
            "FIELD WORKSPACE · OFFLINE READY",
            header.findViewById<TextView>(R.id.collectra_workspace_badge).text,
        )
        assertNotNull(navigation.findViewById<View>(R.id.collectra_nav_shell).background)
    }

    @Test
    fun `form and install screens retain required interaction controls`() {
        val form = inflater.inflate(R.layout.screen_form_entry, null)
        val install = inflater.inflate(R.layout.install_confirm_fragment, null)

        assertNotNull(form.findViewById<View>(R.id.nav_btn_prev))
        assertNotNull(form.findViewById<View>(R.id.nav_btn_next))
        assertNotNull(form.findViewById<View>(R.id.nav_btn_finish))
        assertNotNull(install.findViewById<View>(R.id.btn_start_install))
        assertNotNull(install.findViewById<View>(R.id.btn_stop_install))
    }

    @Test
    fun `home logout action uses Collectra identity`() {
        assertEquals("Log out of Collectra", Localization.get("home.logout"))
    }
}
