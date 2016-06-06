#! /bin/sh

cd android
cp -f ../../cn1/Themes/androidTheme.res .
zip -0 ../android.skin *

cd ../feature_phone
zip -0 ../feature_phone.skin *

cd ../ipad
cp -f ../../cn1/Themes/iPhoneTheme.res .
zip -0 ../ipad.skin *

cd ../ipad3
cp -f ../../cn1/Themes/iPhoneTheme.res .
zip -0 ../ipad3.skin *

cd ../iphone4
cp -f ../../cn1/Themes/iPhoneTheme.res .
zip -0 ../iphone4.skin *

cd ../iphone5
cp -f ../../cn1/Themes/iPhoneTheme.res .
zip -0 ../iphone5.skin *

cd ../iphone5_os7
cp -f ../../cn1/Themes/iOS7Theme.res .
zip -0 ../iphone5_os7.skin *
cp -f ../iphone5_os7.skin ../OTA/iphone5_os7.skin

cd ../iphone3gs_os7
cp -f ../../cn1/Themes/iOS7Theme.res .
zip -0 ../iphone3gs_os7.skin *
cp -f ../iphone3gs_os7.skin ../OTA/iphone3gs_os7.skin

cd ../ipad_os7
cp -f ../../cn1/Themes/iOS7Theme.res .
zip -0 ../ipad_os7.skin *
cp -f ../ipad_os7.skin ../OTA/ipad_os7.skin

cd ../OTA/ipad3_os7
cp -f ../../../cn1/Themes/iOS7Theme.res .
zip -0 ../ipad3_os7.skin *

cd ../../iphone4_os7
cp -f ../../cn1/Themes/iOS7Theme.res .
zip -0 ../iphone4_os7.skin *
cp -f ../iphone4_os7.skin ../OTA/iphone4_os7.skin

cd ../OTA/iphone6Plus
cp -f ../../../cn1/Themes/iOS7Theme.res .
zip -0 ../iphone6Plus.skin *
cp -f ../iphone6Plus.skin ../OTA/iphone6Plus.skin

cd ../OTA/iphone6
cp -f ../../../cn1/Themes/iOS7Theme.res .
zip -0 ../iphone6.skin *
cp -f ../iphone6.skin ../OTA/iphone6.skin

cd ../OTA/iphone5_os7
cp -f ../../../cn1/Themes/iOS7Theme.res .
zip -0 ../iphone5_os7.skin *
cp -f ../iphone5_os7.skin ../OTA/iphone5_os7.skin

cd ../OTA/iphone4_os7
cp -f ../../../cn1/Themes/iOS7Theme.res .
zip -0 ../iphone4_os7.skin *
cp -f ../iphone4_os7.skin ../OTA/iphone4_os7.skin

cd ../OTA/ipad3_os7
cp -f ../../../cn1/Themes/iOS7Theme.res .
zip -0 ../ipad3_os7.skin *
cp -f ../ipad3_os7.skin ../OTA/ipad3_os7.skin

cd ../OTA/nexus
cp -f ../../../cn1/Themes/androidTheme.res .
zip -0 ../nexus.skin *

cd ../iphone3gs
cp -f ../../cn1/Themes/iPhoneTheme.res .
zip -0 ../iphone3gs.skin *

cd ../OTA/torch
cp -f ../../../cn1/Themes/blackberry_theme.res .
zip -0 ../torch.skin *

cd ../lumia
cp -f ../../cn1/Themes/winTheme.res .
zip -0 ../lumia.skin *

cd ../OTA/xoom
cp -f ../../../cn1/Themes/android_holo_light.res .
zip -0 ../xoom.skin *

cd ../OTA/HTCOne
cp -f ../../../cn1/Themes/android_holo_light.res .
zip -0 ../HTCOne.skin *

cd ../OTA/SamsungS7
cp -f ../../../cn1/Themes/android_holo_light.res .
zip -0 ../SamsungS7.skin *

cd ../OTA/HTC10
cp -f ../../../cn1/Themes/android_holo_light.res .
zip -0 ../HTC10.skin *

cd ../OTA/Nexus5
cp -f ../../../cn1/Themes/android_holo_light.res .
zip -0 ../Nexus5.skin *


cd ../OTA/NokiaLumia920
cp -f ../../../cn1/Themes/winTheme.res .
zip -0 ../NokiaLumia920.skin *
