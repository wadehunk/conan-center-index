from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.build import check_min_cppstd
from conan.tools.cmake import CMakeToolchain, CMake, CMakeDeps, cmake_layout
from conan.tools.files import apply_conandata_patches, copy, export_conandata_patches, get, rm, rmdir, replace_in_file
from conan.tools.scm import Version
import os

required_conan_version = ">=1.53.0"

class CycloneDDSCXXConan(ConanFile):
    name = "cyclonedds-cxx"
    license = "EPL-2.0"
    homepage = "https://cyclonedds.io/"
    url = "https://github.com/conan-io/conan-center-index"
    description = "Eclipse Cyclone DDS C++ Binding- An implementation"\
                  " of the OMG Data Distribution Service (DDS) specification"
    topics = ("dds", "ipc", "ros", "middleware")
    package_type = "library"
    settings = "os", "arch", "compiler", "build_type"
    options = {
        "shared": [True, False],
        "fPIC": [True, False],
    }
    default_options = {
        "shared": False,
        "fPIC": True,
    }
    short_paths = True

    @property
    def _min_cppstd(self):
        return "17"

    @property
    def _compilers_minimum_version(self):
        return {
            "gcc": "7",
            "Visual Studio": "16",
            "msvc": "192",
            "clang": "7",
            "apple-clang": "10",
        }

    def _has_idlc(self, info=False):
        # don't build idllib when it makes little sense or not supported
        host_os = self.info.settings.os if info else self.settings.os
        return host_os not in ["Android", "iOS", "watchOS", "tvOS", "Neutrino"]

    def export_sources(self):
        copy(self, os.path.join("cmake", "CycloneDDS-CXX_idlcxx.cmake"), self.recipe_folder, self.export_sources_folder)
        export_conandata_patches(self)

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def configure(self):
        if self.options.shared:
            self.options.rm_safe("fPIC")

    def layout(self):
        cmake_layout(self,src_folder="src")

    def requirements(self):
        # Use the corresponding version of cyclonedds
        self.requires("cyclonedds/{}".format(self.version))

    def validate(self):
        if self.settings.compiler.get_safe("cppstd"):
            check_min_cppstd(self, self._min_cppstd)
        minimum_version = self._compilers_minimum_version.get(str(self.settings.compiler), False)
        if minimum_version and Version(self.settings.compiler.version) < minimum_version:
            raise ConanInvalidConfiguration(
                f"{self.ref} requires C++{self._min_cppstd}, which your compiler does not support."
            )

    def build_requirements(self):
        self.tool_requires("cmake/[>=3.16 <4]")

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def generate(self):
        tc = CMakeToolchain(self)
        tc.variables["BUILD_DDSLIB"] = True
        tc.variables["BUILD_IDLLIB"] = self._has_idlc()
        tc.variables["BUILD_DOCS"] = False
        tc.variables["BUILD_TESTING"] = False
        tc.variables["BUILD_EXAMPLES"] = False
        # variables which effects build
        tc.variables["ENABLE_LEGACY"] = False
        tc.variables["ENABLE_SHM"] = self.dependencies["cyclonedds"].options.with_shm
        tc.variables["ENABLE_TYPE_DISCOVERY"] = self.dependencies["cyclonedds"].options.enable_discovery
        tc.variables["ENABLE_TOPIC_DISCOVERY"] = self.dependencies["cyclonedds"].options.enable_discovery
        tc.variables["ENABLE_COVERAGE"] = False
        tc.generate()
        cd = CMakeDeps(self)
        cd.generate()

    def _patch_sources(self):
        #apply_conandata_patches(self)
        cmakelists = os.path.join(self.source_folder, "CMakeLists.txt")
        replace_in_file(self, cmakelists,
                        "get_target_property(cyclonedds_has_shm CycloneDDS::ddsc SHM_SUPPORT_IS_AVAILABLE)",
                        "set(cyclonedds_has_shm {})".format(self.dependencies["cyclonedds"].options.with_shm))
        replace_in_file(self, cmakelists,
                        "get_target_property(cyclonedds_has_type_discovery CycloneDDS::ddsc TYPE_DISCOVERY_IS_AVAILABLE)",
                        "set(cyclonedds_has_type_discovery {})".format(self.dependencies["cyclonedds"].options.enable_discovery))
        replace_in_file(self, cmakelists,
                        "get_target_property(cyclonedds_has_topic_discovery CycloneDDS::ddsc TOPIC_DISCOVERY_IS_AVAILABLE)",
                        "set(cyclonedds_has_topic_discovery {})".format(self.dependencies["cyclonedds"].options.enable_discovery))

    def build(self):
        self._patch_sources()
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def package(self):
        cmake = CMake(self)
        cmake.install()
        rmdir(self, os.path.join(self.package_folder, "share"))
        rmdir(self, os.path.join(self.package_folder, "lib", "pkgconfig"))
        rm(self, "*.cmake", os.path.join(self.package_folder, "lib", "cmake", "CycloneDDS-CXX"))
        copy(self, "LICENSE", self.source_folder, os.path.join(self.package_folder, "licenses"))
        copy(self, "CycloneDDS-CXX_idlcxx.cmake",
                   src=os.path.join(self.source_folder, os.pardir, "cmake"),
                   dst=os.path.join(self.package_folder, self._module_path, "CycloneDDS-CXX"))
        if self.settings.os == "Windows":
            for p in ("*.pdb", "concrt*.dll", "msvcp*.dll", "vcruntime*.dll"):
                rm(self, p, os.path.join(self.package_folder, "bin"))

    @property
    def _module_path(self):
        return os.path.join("lib", "cmake")

    def package_info(self):
        self.cpp_info.set_property("cmake_find_mode", "both")
        self.cpp_info.set_property("cmake_module_file_name", "CycloneDDS-CXX")
        self.cpp_info.set_property("cmake_file_name", "CycloneDDS-CXX")
        self.cpp_info.set_property("cmake_target_name", "CycloneDDS-CXX::CycloneDDS-CXX")
        self.cpp_info.set_property("pkg_config_name", "CycloneDDS-CXX")

        # Provide CycloneDDS-CXX::idlcxx target
        build_modules = [
            os.path.join(self._module_path, "CycloneDDS-CXX", "CycloneDDS-CXX_idlcxx.cmake"),
            os.path.join(self._module_path, "CycloneDDS-CXX", "idlcxx", "Generate.cmake"),
        ]
        self.cpp_info.set_property("cmake_build_modules", build_modules)

        # TODO: to remove in conan v2
        self.cpp_info.filenames["cmake_find_package"] = "CycloneDDS-CXX"
        self.cpp_info.filenames["cmake_find_package_multi"] = "CycloneDDS-CXX"
        self.cpp_info.names["cmake_find_package"] = "CycloneDDS-CXX"
        self.cpp_info.names["cmake_find_package_multi"] = "CycloneDDS-CXX"
        self.cpp_info.includedirs = ["include/ddscxx"]
        self.cpp_info.components["ddscxx"].libs = ["ddscxx"]
        self.cpp_info.components["ddscxx"].includedirs = ["include/ddscxx"]
        self.cpp_info.components["ddscxx"].names["cmake_find_package"] = "ddscxx"
        self.cpp_info.components["ddscxx"].names["cmake_find_package_multi"] = "ddscxx"
        # self.cpp_info.components["ddscxx"].requires = ["CycloneDDS::ddsc"]
        self.cpp_info.components["ddscxx"].set_property("cmake_target_name", "CycloneDDS-CXX::ddscxx")
        self.cpp_info.components["ddscxx"].set_property("pkg_config_name", "CycloneDDS-CXX")
