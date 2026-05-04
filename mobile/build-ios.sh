#!/bin/bash
set -e

echo "========================================"
echo " DeepDerm iOS Build Setup Script"
echo "========================================"

cd "$(dirname "$0")"

# ── Step 1: Run Expo prebuild (incremental) ───────────────────────────────────
echo ""
echo "Step 1: Running Expo prebuild..."
echo "y" | npx expo prebuild --platform ios

# ── Step 1.2: Patch Podfile for C++20 (NitroModules Xcode 26 fix) ────────────
echo ""
echo "Step 1.2: Patching Podfile for C++20 standard..."
python3 - << 'PYEOF'
with open('ios/Podfile', 'r') as f:
    content = f.read()

patch = """
    installer.pods_project.targets.each do |target|
      target.build_configurations.each do |config|
        config.build_settings['CLANG_CXX_LANGUAGE_STANDARD'] = 'c++20'
      end
    end
"""

if 'CLANG_CXX_LANGUAGE_STANDARD' not in content:
    # Inject before the final 'end' of the post_install block
    content = content.replace("    )\n  end\nend", "    )\n" + patch + "  end\nend")
    with open('ios/Podfile', 'w') as f:
        f.write(content)
    print("  Injected C++20 patch into Podfile.")
else:
    print("  C++20 patch already exists in Podfile.")
PYEOF

# ── Step 1.5: Run pod install ────────────────────────────────────────────────
echo ""
echo "Step 1.5: Running pod install..."
cd ios && pod install && cd ..

# ── Step 2: Fix entitlements (remove Push Notifications) ─────────────────────
echo ""
echo "Step 2: Removing Push Notifications entitlement..."
cat > ios/DeepDermHasta/DeepDermHasta.entitlements << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
  </dict>
</plist>
EOF
echo "  Done."

# ── Step 3: Patch fmt for Xcode 26 (Apple Clang 21) ─────────────────────────
echo ""
echo "Step 3: Patching fmt library for Xcode 26 (Apple Clang 21)..."
chmod u+w ios/Pods/fmt/include/fmt/base.h
sed -i '' \
  's/#elif defined(__apple_build_version__) && __apple_build_version__ < 14000029L/#elif defined(__apple_build_version__) \&\& (__apple_build_version__ < 14000029L || __apple_build_version__ >= 21000000L)/' \
  ios/Pods/fmt/include/fmt/base.h
echo "  Done: $(grep apple_build_version ios/Pods/fmt/include/fmt/base.h | tail -1)"

# ── Step 4: Remove SplashScreen storyboard reference ─────────────────────────
echo ""
echo "Step 4: Removing SplashScreen.storyboard references from Xcode project..."
python3 - << 'PYEOF'
import re

with open('ios/DeepDermHasta.xcodeproj/project.pbxproj', 'r') as f:
    content = f.read()

content = re.sub(r'[ \t]+3E461D99554A48A4959DE609 /\* SplashScreen\.storyboard in Resources \*/ = \{[^}]+\};\n', '', content)
content = re.sub(r'[ \t]+AA286B85B6C04FC6940260E9 /\* SplashScreen\.storyboard \*/ = \{[^}]+\};\n', '', content)
content = re.sub(r'[ \t]+AA286B85B6C04FC6940260E9 /\* SplashScreen\.storyboard \*/,\n', '', content)
content = re.sub(r'[ \t]+3E461D99554A48A4959DE609 /\* SplashScreen\.storyboard in Resources \*/,\n', '', content)

with open('ios/DeepDermHasta.xcodeproj/project.pbxproj', 'w') as f:
    f.write(content)

print(f"  Remaining SplashScreen references: {content.count('SplashScreen.storyboard')}")
PYEOF

# ── Step 5: Replace UILaunchStoryboardName with UILaunchScreen in Info.plist ─
echo ""
echo "Step 5: Updating Info.plist to use UILaunchScreen..."
python3 - << 'PYEOF'
with open('ios/DeepDermHasta/Info.plist', 'r') as f:
    content = f.read()

old = '\t<key>UILaunchStoryboardName</key>\n\t<string>SplashScreen</string>'
new = '\t<key>UILaunchScreen</key>\n\t<dict>\n\t</dict>'
if old in content:
    content = content.replace(old, new)
    print("  Replaced UILaunchStoryboardName with UILaunchScreen dict.")
else:
    print("  UILaunchStoryboardName not found (may already be patched).")

with open('ios/DeepDermHasta/Info.plist', 'w') as f:
    f.write(content)
PYEOF

# ── Step 6: Build ─────────────────────────────────────────────────────────────
echo ""
echo "========================================"
echo " Setup complete! Now building incrementally..."
echo "========================================"
echo ""
npx expo run:ios -d
