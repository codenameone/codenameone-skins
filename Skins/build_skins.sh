#! /bin/sh

cd android
cp -f ../../Themes/androidTheme.res .
zip ../android.skin *

cd ../feature_phone
zip ../feature_phone.skin *

cd ../ipad
cp -f ../../Themes/iPhoneTheme.res .
zip ../ipad.skin *

cd ../iphone4
cp -f ../../Themes/iPhoneTheme.res .
zip ../iphone4.skin *

cd ../nexus
cp -f ../../Themes/androidTheme.res .
zip ../nexus.skin *

cd ../iphone3gs
cp -f ../../Themes/iPhoneTheme.res .
zip ../iphone3gs.skin *
