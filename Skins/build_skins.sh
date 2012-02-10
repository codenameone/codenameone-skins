#! /bin/sh

cd android
cp -f ../../Themes/androidTheme.res .
zip -0 ../android.skin *

cd ../feature_phone
zip -0 ../feature_phone.skin *

cd ../ipad
cp -f ../../Themes/iPhoneTheme.res .
zip -0 ../ipad.skin *

cd ../iphone4
cp -f ../../Themes/iPhoneTheme.res .
zip -0 ../iphone4.skin *

cd ../nexus
cp -f ../../Themes/androidTheme.res .
zip -0 ../nexus.skin *

cd ../iphone3gs
cp -f ../../Themes/iPhoneTheme.res .
zip -0 ../iphone3gs.skin *

cd ../torch
cp -f ../../Themes/blackberry_theme.res .
zip -0 ../torch.skin *
