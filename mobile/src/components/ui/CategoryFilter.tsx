import React, { useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { ui } from '../../design/tokens';
import type { ContentItem } from '../../types';

type Props = {
  categories: string[];
  selected: string;
  items: ContentItem[];
  onSelect: (category: string) => void;
};

/** Three readable quick filters, with all remaining categories in a sheet. */
export default function CategoryFilter({ categories, selected, items, onSelect }: Props) {
  const [visible, setVisible] = useState(false);
  const options = Array.from(new Set(['전체', ...categories.filter((value) => value !== '전체')]));
  const mostFrequent = options
    .filter((value) => value !== '전체')
    .map((value) => ({ value, count: items.filter((item) => item.category.includes(value)).length }))
    .sort((a, b) => b.count - a.count || a.value.localeCompare(b.value, 'ko'));
  const primary = mostFrequent.slice(0, 2).map(({ value }) => value);
  if (selected !== '전체' && !primary.includes(selected)) primary.push(selected);
  const quick = ['전체', ...primary];
  const choose = (value: string) => {
    onSelect(value);
    setVisible(false);
  };

  return (
    <View style={styles.container} testID="library-category-filter">
      <View style={styles.row}>
        <ScrollView
          horizontal
          style={styles.quickFilterScroll}
          contentContainerStyle={styles.quickFilterContent}
          showsHorizontalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          {quick.map((value) => (
          <Pressable
            key={value}
            onPress={() => choose(value)}
            style={[styles.chip, selected === value && styles.chipActive]}
            accessibilityRole="button"
            accessibilityState={{ selected: selected === value }}
            accessibilityLabel={`${value} 필터`}
          >
            <Text style={[styles.chipLabel, selected === value && styles.chipLabelActive]} numberOfLines={1}>
              {value}
            </Text>
          </Pressable>
          ))}
        </ScrollView>
        {mostFrequent.length > 2 ? (
          <Pressable
            style={styles.allButton}
            onPress={() => setVisible(true)}
            accessibilityRole="button"
            accessibilityLabel="전체 카테고리 보기"
          >
            <Ionicons name="options-outline" size={16} color={ui.color.brand} />
            <Text style={styles.allButtonLabel}>전체 카테고리</Text>
          </Pressable>
        ) : null}
      </View>

      <Modal visible={visible} animationType="slide" transparent onRequestClose={() => setVisible(false)}>
        <View style={styles.modalRoot}>
          <Pressable style={styles.overlay} onPress={() => setVisible(false)} accessibilityLabel="필터 닫기" />
          <View style={styles.sheet}>
            <View style={styles.sheetHead}>
              <View>
                <Text style={styles.sheetTitle}>카테고리 선택</Text>
                <Text style={styles.sheetSub}>보고 싶은 주제를 골라 주세요.</Text>
              </View>
              <Pressable style={styles.close} onPress={() => setVisible(false)} accessibilityRole="button" accessibilityLabel="닫기">
                <Ionicons name="close" size={22} color={ui.color.foreground} />
              </Pressable>
            </View>
            <ScrollView style={styles.options} contentContainerStyle={styles.optionsContent} showsVerticalScrollIndicator={false}>
              {options.map((value) => {
                const count = value === '전체' ? items.length : items.filter((item) => item.category.includes(value)).length;
                return (
                  <Pressable key={value} style={styles.option} onPress={() => choose(value)} accessibilityRole="button" accessibilityState={{ selected: selected === value }}>
                    <Text style={[styles.optionText, selected === value && styles.optionSelected]} numberOfLines={2}>{value}</Text>
                    <Text style={styles.optionCount}>{count}개</Text>
                    {selected === value && <Ionicons name="checkmark-circle" size={20} color={ui.color.brand} />}
                  </Pressable>
                );
              })}
            </ScrollView>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { marginTop: 4, marginBottom: 12, gap: 0 },
  quickFilterScroll: { flex: 1, minWidth: 0 },
  quickFilterContent: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingRight: 6, paddingVertical: 2 },
  row: { flexDirection: 'row', alignItems: 'center', width: '100%', gap: 10 },

  chip: { maxWidth: 142, minHeight: 38, flexShrink: 0, paddingHorizontal: 13, paddingVertical: 8, backgroundColor: ui.color.white, borderRadius: ui.radius.pill, borderWidth: 1, borderColor: ui.color.border, justifyContent: 'center', overflow: 'hidden' },

  chipActive: { backgroundColor: ui.color.brand, borderColor: ui.color.brand },
  chipLabel: { fontSize: 12, fontWeight: '700', color: '#4C5362' },
  chipLabelActive: { color: ui.color.white },
  allButton: { minHeight: 38, flexShrink: 0, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 5, paddingHorizontal: 10, borderRadius: 12, borderWidth: 1, borderColor: '#D7E5FF', backgroundColor: '#EDF3FF', marginLeft: 2 },

  allButtonLabel: { fontSize: 11, fontWeight: '800', color: ui.color.brand },

  modalRoot: { flex: 1, justifyContent: 'flex-end' },
  overlay: { ...StyleSheet.absoluteFillObject, backgroundColor: 'rgba(11,15,22,0.44)' },
  sheet: { maxHeight: '76%', minHeight: 260, borderTopLeftRadius: 24, borderTopRightRadius: 24, backgroundColor: ui.color.surface, paddingHorizontal: 20, paddingTop: 20, paddingBottom: 32 },
  sheetHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, gap: 10 },
  sheetTitle: { color: ui.color.foreground, fontSize: 18, fontWeight: '800' },
  sheetSub: { color: '#555E6C', fontSize: 13, marginTop: 5 },
  close: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  options: { flexGrow: 0 },
  optionsContent: { paddingBottom: 8 },
  option: { minHeight: 52, flexDirection: 'row', alignItems: 'center', gap: 10, borderBottomWidth: 1, borderBottomColor: ui.color.border, paddingVertical: 10 },
  optionText: { color: ui.color.foreground, fontSize: 14, fontWeight: '600', flex: 1 },
  optionSelected: { color: ui.color.brand, fontWeight: '800' },
  optionCount: { color: '#596270', fontSize: 13 },
});

// SAVEON_BRAND_PALETTE_V1

// SAVEON_CATEGORY_FILTER_VISIBILITY_V1_1

// SAVEON_LIBRARY_MICRO_POLISH_V1
