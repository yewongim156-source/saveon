import React from 'react';
import { StyleSheet, View, type ViewProps } from 'react-native';
import { ui } from '../../design/tokens';

type Props = ViewProps & {
  children: React.ReactNode;
};

export default function AppCard({ children, style, ...props }: Props) {
  return (
    <View style={[styles.base, style]} {...props}>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  base: {
    padding: ui.spacing.md,
    borderRadius: ui.radius.lg,
    borderWidth: 1,
    borderColor: ui.color.border,
    backgroundColor: ui.color.surface,
  },
});
