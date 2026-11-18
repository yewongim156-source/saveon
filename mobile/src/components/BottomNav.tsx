import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { theme } from '../theme';

type Tab = 'home' | 'save' | 'library' | 'search' | 'more';

type Props = {
  active: Tab;
  onChange: (tab: Tab) => void;
};

const tabs: {
  key: Tab;
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
}[] = [
  { key: 'home', label: '홈', icon: 'home-outline' },
  { key: 'save', label: '저장', icon: 'add-circle-outline' },
  { key: 'library', label: '보관함', icon: 'albums-outline' },
  { key: 'search', label: '검색', icon: 'search-outline' },
  { key: 'more', label: '모아보기', icon: 'grid-outline' },
];

export default function BottomNav({
  active,
  onChange,
}: Props) {
  return (
    <View style={styles.wrap}>
      {tabs.map((tab) => {
        const selected = active === tab.key;

        return (
          <Pressable
            key={tab.key}
            style={styles.item}
            onPress={() => onChange(tab.key)}
            accessibilityRole="tab"
            accessibilityState={{ selected }}
            accessibilityLabel={tab.label}
          >
            <Ionicons
              name={tab.icon}
              size={22}
              color={
                selected
                  ? theme.primary
                  : theme.muted
              }
            />

            <Text
              style={[
                styles.label,
                selected && styles.selected,
              ]}
            >
              {tab.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: 'row',
    borderTopWidth: 1,
    borderTopColor: theme.line,
    backgroundColor: theme.card,
    paddingBottom: 10,
    paddingTop: 8,
  },
  item: {
    minHeight: 48,
    justifyContent: 'center',
    flex: 1,
    alignItems: 'center',
    gap: 3,
  },
  label: {
    fontSize: 10,
    color: theme.muted,
  },
  selected: {
    color: theme.primary,
    fontWeight: '700',
  },
});

// SAVEON_HOME_UX_V1
