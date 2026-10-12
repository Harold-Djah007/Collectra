package org.commcare.activities

import android.content.Context
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.TextView
import androidx.test.core.app.ApplicationProvider
import org.commcare.dalvik.R
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [28], application = org.commcare.CommCareTestApplication::class)
class CollectraWorkspaceDesignTest {
    @Test
    fun `workspace actions grow with large text and retain existing action ids`() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val configuration = android.content.res.Configuration(context.resources.configuration)
        configuration.fontScale = 2f
        val themed = android.view.ContextThemeWrapper(context.createConfigurationContext(configuration), R.style.CommonTheme)
        val root = LayoutInflater.from(themed).inflate(R.layout.collectra_home_masthead, null)
        for (id in listOf(R.id.collectra_today_start, R.id.collectra_today_resume, R.id.collectra_today_sync)) {
            val button = root.findViewById<Button>(id)
            assertEquals(ViewGroup.LayoutParams.WRAP_CONTENT, button.layoutParams.height)
            assertTrue(button.minimumHeight >= 56 * context.resources.displayMetrics.density)
        }
        assertNotNull(root.findViewById<TextView>(R.id.collectra_today_sync_status))
    }

    @Test
    fun `launcher splash and visible headers use the Collectra mark`() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val themed = android.view.ContextThemeWrapper(context, R.style.CommonTheme)
        val root = LayoutInflater.from(themed).inflate(R.layout.collectra_splash, null)
        assertNotNull(root.findViewById<View>(R.id.collectra_splash_mark))
        assertEquals(context.getString(R.string.collectra_brand_name), root.findViewById<TextView>(R.id.collectra_splash_title).text)
        assertNotNull(context.getDrawable(R.mipmap.collectra_launcher))
        assertNotNull(context.getDrawable(R.drawable.collectra_mark))
    }
}
