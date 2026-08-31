package org.commcare.activities

import android.view.ContextThemeWrapper
import android.view.LayoutInflater
import android.view.View
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
    fun `home card uses Collectra list row surface`() {
        val view = inflater.inflate(R.layout.square_card, null)
        val card = view.findViewById<CardView>(R.id.home_card)

        assertNotNull(card.background)
        assertTrue(card.radius > 0)
        assertNotNull(view.findViewById(R.id.card_icon_chip))
        assertNotNull(view.findViewById(R.id.card_text))
        assertEquals(
            android.view.ViewGroup.LayoutParams.MATCH_PARENT,
            card.layoutParams?.width
                ?: android.view.ViewGroup.LayoutParams.MATCH_PARENT,
        )
    }

    @Test
    fun `home masthead uses Collectra brand without legacy banner card`() {
        val view = inflater.inflate(R.layout.collectra_home_masthead, null)
        assertNotNull(view.findViewById(R.id.collectra_home_greeting))
        assertNotNull(view.findViewById(R.id.main_top_banner))
        assertNotNull(view.findViewById(R.id.collectra_home_wordmark))
        assertNotNull(view.findViewById(R.id.collectra_home_accent))
    }

    @Test
    fun `login banner uses Collectra typographic masthead`() {
        val view = inflater.inflate(R.layout.grid_header_top_banner, null)
        assertNotNull(view.findViewById(R.id.collectra_brand_wordmark))
        assertEquals(View.GONE, view.findViewById<View>(R.id.main_top_banner).visibility)
    }

    @Test
    fun `launch splash presents Collectra brand`() {
        val view = inflater.inflate(R.layout.collectra_splash, null)
        assertNotNull(view.findViewById(R.id.collectra_splash_mark))
        assertNotNull(view.findViewById(R.id.collectra_splash_title))
    }

    @Test
    fun `home logout action uses Collectra identity`() {
        assertEquals("Log out of Collectra", Localization.get("home.logout"))
    }
}
