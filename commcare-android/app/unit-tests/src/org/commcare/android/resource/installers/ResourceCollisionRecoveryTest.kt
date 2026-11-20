package org.commcare.android.resource.installers

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

class ResourceCollisionRecoveryTest {
    @get:Rule
    val temporaryFolder = TemporaryFolder()

    @Test
    fun preservesInstalledResourceWhenPromotingDownloadedUpdate() {
        val installed = temporaryFolder.newFile("suite.xml").apply { writeText("version-24") }
        val incoming = temporaryFolder.newFile("staged-suite.xml").apply { writeText("version-31") }

        assertTrue(FileSystemUtils.moveAsideConflictAndPromote(incoming, installed))
        assertEquals("version-31", installed.readText())
        assertFalse(incoming.exists())

        val preserved = temporaryFolder.root.listFiles()!!.filter {
            it.name.startsWith("suite.xml.cc_app-conflict-")
        }
        assertEquals(1, preserved.size)
        assertEquals("version-24", preserved.single().readText())
    }

    @Test
    fun refusesMissingIncomingResourceWithoutChangingInstalledFile() {
        val installed = temporaryFolder.newFile("suite.xml").apply { writeText("version-24") }
        val incoming = File(temporaryFolder.root, "missing-suite.xml")

        assertFalse(FileSystemUtils.moveAsideConflictAndPromote(incoming, installed))
        assertEquals("version-24", installed.readText())
    }

    @Test
    fun refusesMissingDestinationWithoutChangingStagedFile() {
        val incoming = temporaryFolder.newFile("staged-suite.xml").apply { writeText("version-31") }
        val installed = File(temporaryFolder.root, "suite.xml")

        assertFalse(FileSystemUtils.moveAsideConflictAndPromote(incoming, installed))
        assertEquals("version-31", incoming.readText())
        assertFalse(installed.exists())
    }

    @Test
    fun restoresOriginalWhenIncomingPromotionFails() {
        val installed = temporaryFolder.newFile("suite.xml").apply { writeText("version-24") }
        val staged = temporaryFolder.newFile("staged-suite.xml").apply { writeText("version-31") }
        val failingSource = object : File(staged.absolutePath) {
            override fun renameTo(dest: File): Boolean = false
        }

        assertFalse(FileSystemUtils.moveAsideConflictAndPromote(failingSource, installed))
        assertEquals("version-24", installed.readText())
        assertEquals("version-31", staged.readText())
    }

    @Test
    fun distinctUpdatesRetainDistinctOriginalCopies() {
        val installed = temporaryFolder.newFile("suite.xml").apply { writeText("version-24") }
        val first = temporaryFolder.newFile("staged-v31.xml").apply { writeText("version-31") }
        val second = temporaryFolder.newFile("staged-v32.xml").apply { writeText("version-32") }

        assertTrue(FileSystemUtils.moveAsideConflictAndPromote(first, installed))
        assertTrue(FileSystemUtils.moveAsideConflictAndPromote(second, installed))
        assertEquals("version-32", installed.readText())
        val backups = temporaryFolder.root.listFiles()!!.filter {
            it.name.startsWith("suite.xml.cc_app-conflict-")
        }
        assertEquals(2, backups.size)
        assertEquals(setOf("version-24", "version-31"), backups.map { it.readText() }.toSet())
    }
}
