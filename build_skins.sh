#! /bin/sh

cd android
cp -f ../../Themes/androidTheme.res .
zip -0 ../android.skin *

cd ../feature_phone
zip -0 ../feature_phone.skin *

cd ../ipad
cp -f ../../Themes/iPhoneTheme.res .
zip -0 ../ipad.skin *

cd ../ipad3
cp -f ../../Themes/iPhoneTheme.res .
zip -0 ../ipad3.skin *

cd ../iphone4
cp -f ../../Themes/iPhoneTheme.res .
zip -0 ../iphone4.skin *

cd ../iphone5
cp -f ../../Themes/iPhoneTheme.res .
zip -0 ../iphone5.skin *

cd ../iphone5_os7
cp -f ../../Themes/iOS7Theme.res .
zip -0 ../iphone5_os7.skin *
cp -f ../iphone5_os7.skin ../OTA/iphone5_os7.skin

cd ../iphone3gs_os7
cp -f ../../Themes/iOS7Theme.res .
zip -0 ../iphone3gs_os7.skin *
cp -f ../iphone3gs_os7.skin ../OTA/iphone3gs_os7.skin

cd ../ipad_os7
cp -f ../../Themes/iOS7Theme.res .
zip -0 ../ipad_os7.skin *
cp -f ../ipad_os7.skin ../OTA/ipad_os7.skin

cd ../ipad3_os7
cp -f ../../Themes/iOS7Theme.res .
zip -0 ../ipad3_os7.skin *
cp -f ../ipad3_os7.skin ../OTA/ipad3_os7.skin

cd ../iphone4_os7
cp -f ../../Themes/iOS7Theme.res .
zip -0 ../iphone4_os7.skin *
cp -f ../iphone4_os7.skin ../OTA/iphone4_os7.skin


cd ../nexus
cp -f ../../Themes/androidTheme.res .
zip -0 ../nexus.skin *

cd ../iphone3gs
cp -f ../../Themes/iPhoneTheme.res .
zip -0 ../iphone3gs.skin *

cd ../torch
cp -f ../../Themes/blackberry_theme.res .
zip -0 ../torch.skin *

cd ../xoom
cp -f ../../Themes/android_holo_light.res .
zip -0 ../xoom.skin *

cd ../lumia
cp -f ../../Themes/winTheme.res .
zip -0 ../lumia.skin *

cd ../OTA/HTCOne
cp -f ../../../Themes/android_holo_light.res .
zip -0 ../HTCOne.skin *

cd ../NokiaLumia920
cp -f ../../../Themes/android_holo_light.res .
zip -0 ../NokiaLumia920.skin *
