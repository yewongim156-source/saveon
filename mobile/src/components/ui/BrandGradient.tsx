import React from 'react';
import { Image, StyleSheet } from 'react-native';

type Variant = 'primary' | 'hero' | 'page' | 'soft';
type Props = { variant?: Variant; radius?: number };

// Bundled assets: no extra Expo dependency, remote fetch, or per-render work.
const backgrounds = {
  primary: require('../../../assets/brand_gradients/primary.png'),
  hero: require('../../../assets/brand_gradients/hero.png'),
  page: require('../../../assets/brand_gradients/page.png'),
  soft: require('../../../assets/brand_gradients/soft.png'),
};

export default function BrandGradient({ variant = 'primary', radius = 14 }: Props) {
  return (
    <Image
      source={backgrounds[variant]}
      resizeMode="stretch"
      accessibilityIgnoresInvertColors
      style={[StyleSheet.absoluteFillObject, { borderRadius: radius }]}
    />
  );
}
