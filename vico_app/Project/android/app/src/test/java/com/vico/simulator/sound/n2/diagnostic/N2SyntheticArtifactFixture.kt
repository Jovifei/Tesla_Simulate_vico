package com.vico.simulator.sound.n2.diagnostic

import com.vico.simulator.sound.HybridTestProfiles
import com.vico.simulator.sound.n2.N2Profile
import com.vico.simulator.sound.n2.N2ProfileArtifactLoader
import java.nio.file.Files
import java.nio.file.Paths
import java.nio.file.StandardOpenOption.CREATE_NEW

/** Test-only input creation. Never a substitute for the separately approved reference artifacts. */
internal object N2SyntheticArtifactFixture {
    @JvmStatic fun main(args: Array<String>) {
        require(args.size == 1) { "usage: NEW_SYNTHETIC_INPUT_DIRECTORY" }
        val root = Files.createDirectory(Paths.get(args[0]))
        Files.write(root.resolve("baseline.bin"), HybridTestProfiles.create().toBytes(), CREATE_NEW)
        Files.write(root.resolve("profile.bin"), N2ProfileArtifactLoader.export(N2Profile.calibrated()).bytes, CREATE_NEW)
        Files.write(root.resolve("TEST_ONLY.txt"),
            "Generated synthetic test inputs. No reference, fitting, held-out or acoustic acceptance.\n".toByteArray(), CREATE_NEW)
    }
}
