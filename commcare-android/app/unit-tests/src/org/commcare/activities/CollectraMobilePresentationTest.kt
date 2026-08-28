package org.commcare.activities

import android.view.ContextThemeWrapper
import android.view.LayoutInflater
import android.view.View
import androidx.cardview.widget.CardView
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.commcare.CommCareTestApplication
import org.commcare.dalvik.R
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
    }
}
