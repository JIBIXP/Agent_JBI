// Build dir hors de OneDrive (Desktop est synchronisé et verrouille les fichiers).
val externalBuildDir: Directory = rootProject.layout.projectDirectory.dir("C:/Users/ulric/gradle-build/focusguard")
rootProject.layout.buildDirectory.value(externalBuildDir)

subprojects {
    project.layout.buildDirectory.value(externalBuildDir.dir(project.name))
}
subprojects {
    project.evaluationDependsOn(":app")
}

tasks.register<Delete>("clean") {
    delete(rootProject.layout.buildDirectory)
}
