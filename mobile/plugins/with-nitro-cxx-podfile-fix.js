const fs = require('fs');
const path = require('path');
const { withDangerousMod } = require('@expo/config-plugins');

const MARKER = 'React/Nitro/VisionCamera C++ modules need explicit scanner header paths';

const CXX_TARGET_PATCH = `
    cxx_module_targets = [
      'RCT-Folly',
      'React-Core',
      'React-jsi',
      'React-jsinspector',
      'React-jsinspectorcdp',
      'React-jsinspectornetwork',
      'React-jsinspectortracing',
      'NitroModules',
      'NitroImage',
      'VisionCamera',
      'VisionCameraFaceDetector'
    ]
    cxx_dependency_header_search_paths = [
      '$(inherited)',
      '$(PODS_ROOT)/../../node_modules/react-native/ReactCommon',
      '$(PODS_ROOT)/../../node_modules/react-native/ReactCommon/callinvoker',
      '$(PODS_ROOT)/Headers/Public/React-callinvoker',
      '$(PODS_ROOT)/../../node_modules/react-native/ReactCommon/jsinspector-modern',
      '$(PODS_ROOT)/../../node_modules/react-native/ReactCommon/jsinspector-modern/network',
      '$(PODS_ROOT)/../../node_modules/react-native/ReactCommon/jsinspector-modern/tracing',
      '$(PODS_ROOT)/RCT-Folly',
      '$(PODS_ROOT)/Headers/Public/RCT-Folly',
      '$(PODS_ROOT)/Headers/Private/RCT-Folly',
      '$(PODS_ROOT)/DoubleConversion',
      '$(PODS_ROOT)/Headers/Public/DoubleConversion',
      '$(PODS_ROOT)/boost',
      '$(PODS_ROOT)/Headers/Public/boost',
      '$(PODS_ROOT)/fast_float/include',
      '$(PODS_ROOT)/Headers/Public/fast_float',
      '$(PODS_ROOT)/fmt/include',
      '$(PODS_ROOT)/glog',
      '$(PODS_ROOT)/SocketRocket'
    ]

    installer.pods_project.targets.each do |target|
      target.build_configurations.each do |config|
        config.build_settings['CLANG_CXX_LANGUAGE_STANDARD'] = 'c++20'
      end

      # ${MARKER}
      # Xcode's explicit module scanner can otherwise scan the CocoaPods dummy
      # .m file as plain ObjC and fail to find libc++ or transitive C++ headers.
      if cxx_module_targets.include?(target.name)
        target.build_configurations.each do |config|
          config.build_settings['CLANG_CXX_LIBRARY'] = 'libc++'
          config.build_settings['SWIFT_OBJC_INTEROP_MODE'] = 'objcxx'

          header_search_paths = config.build_settings['HEADER_SEARCH_PATHS']
          header_search_paths = header_search_paths.is_a?(String) ? header_search_paths.split(' ') : Array(header_search_paths)
          config.build_settings['HEADER_SEARCH_PATHS'] = (header_search_paths + cxx_dependency_header_search_paths).uniq
        end

        target.source_build_phase.files.each do |build_file|
          file_path = build_file.file_ref&.path
          next unless file_path&.end_with?('-dummy.m')

          build_file.settings ||= {}
          flags = build_file.settings['COMPILER_FLAGS']
          flags = flags.is_a?(String) ? flags.split(' ') : Array(flags)
          flags += ['-x', 'objective-c++']
          build_file.settings['COMPILER_FLAGS'] = flags.uniq.join(' ')
        end
      end
    end
`;

function patchPodfile(contents) {
  if (contents.includes(MARKER)) {
    return contents;
  }

  const existingCxxModulePatch = /    cxx_module_targets = \[[\s\S]*?\n    end\n(?=  end\nend)/m;
  if (existingCxxModulePatch.test(contents)) {
    return contents.replace(existingCxxModulePatch, CXX_TARGET_PATCH);
  }

  const cxx20OnlyBlock = /    installer\.pods_project\.targets\.each do \|target\|\n      target\.build_configurations\.each do \|config\|\n        config\.build_settings\['CLANG_CXX_LANGUAGE_STANDARD'\] = 'c\+\+20'\n      end\n    end\n/;

  if (cxx20OnlyBlock.test(contents)) {
    return contents.replace(cxx20OnlyBlock, CXX_TARGET_PATCH);
  }

  const postInstallCall = /    react_native_post_install\(\n      installer,\n      config\[:reactNativePath\],\n      :mac_catalyst_enabled => false,\n      :ccache_enabled => ccache_enabled\?\(podfile_properties\),\n    \)\n/;

  if (postInstallCall.test(contents)) {
    return contents.replace(postInstallCall, (match) => `${match}\n${CXX_TARGET_PATCH}`);
  }

  throw new Error('Unable to locate react_native_post_install block in ios/Podfile');
}

module.exports = function withNitroCxxPodfileFix(config) {
  return withDangerousMod(config, [
    'ios',
    async (modConfig) => {
      const podfilePath = path.join(modConfig.modRequest.platformProjectRoot, 'Podfile');
      const contents = fs.readFileSync(podfilePath, 'utf8');
      fs.writeFileSync(podfilePath, patchPodfile(contents));
      return modConfig;
    },
  ]);
};
