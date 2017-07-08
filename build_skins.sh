#! /bin/sh

cd android
cp -f ../../cn1/Themes/androidTheme.res .
zip ../android.skin *

cd ../feature_phone
zip ../feature_phone.skin *

cd ../ipad
cp -f ../../cn1/Themes/iPhoneTheme.res .
zip ../ipad.skin *

cd ../ipad3
cp -f ../../cn1/Themes/iPhoneTheme.res .
zip ../ipad3.skin *

cd ../iphone4
cp -f ../../cn1/Themes/iPhoneTheme.res .
zip ../iphone4.skin *

cd ../iphone5
cp -f ../../cn1/Themes/iPhoneTheme.res .
zip ../iphone5.skin *

cd ../iphone5_os7
cp -f ../../cn1/Themes/iOS7Theme.res .
zip ../iphone5_os7.skin *

cd ../iphone3gs_os7
cp -f ../../cn1/Themes/iOS7Theme.res .
zip ../iphone3gs_os7.skin *

cd ../ipad_os7
cp -f ../../cn1/Themes/iOS7Theme.res .
zip ../ipad_os7.skin *

cd ../ipad3_os7
cp -f ../../cn1/Themes/iOS7Theme.res .
zip ../ipad3_os7.skin *

cd ../iphone4_os7
cp -f ../../cn1/Themes/iOS7Theme.res .
zip ../iphone4_os7.skin *

cd ../iphone6Plus
cp -f ../../cn1/Themes/iOS7Theme.res .
zip ../iphone6Plus.skin *

cd ../iphone6
cp -f ../../cn1/Themes/iOS7Theme.res .
zip ../iphone6.skin *

cd ../iphone5_os7
cp -f ../../cn1/Themes/iOS7Theme.res .
zip ../iphone5_os7.skin *

cd ../iphone4_os7
cp -f ../../cn1/Themes/iOS7Theme.res .
zip ../iphone4_os7.skin *

cd ../ipad3_os7
cp -f ../../cn1/Themes/iOS7Theme.res .
zip ../ipad3_os7.skin *

cd ../nexus
cp -f ../../cn1/Themes/androidTheme.res .
zip ../nexus.skin *

cd ../iphone3gs
cp -f ../../cn1/Themes/iPhoneTheme.res .
zip ../iphone3gs.skin *

cd ../torch
cp -f ../../cn1/Themes/blackberry_theme.res .
zip ../torch.skin *

cd ../lumia
cp -f ../../cn1/Themes/winTheme.res .
zip ../lumia.skin *

cd ../xoom
cp -f ../../cn1/Themes/android_holo_light.res .
zip ../xoom.skin *

cd ../HTCOne
cp -f ../../cn1/Themes/android_holo_light.res .
zip ../HTCOne.skin *

cd ../SamsungS7
cp -f ../../cn1/Themes/android_holo_light.res .
zip ../SamsungS7.skin *

cd ../HTC10
cp -f ../../cn1/Themes/android_holo_light.res .
zip ../HTC10.skin *

cd ../Nexus5
cp -f ../../cn1/Themes/android_holo_light.res .
zip ../Nexus5.skin *

cd ../NokiaLumia920
cp -f ../../cn1/Themes/winTheme.res .
zip ../NokiaLumia920.skin *

cd ../K7
cp -f ../../cn1/Themes/android_holo_light.res .
zip ../K7.skin *

cd ..
cp *.skin OTA
