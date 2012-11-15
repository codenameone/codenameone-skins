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
