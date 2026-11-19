package com.saveon.api.conflict;

import java.text.Normalizer;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Conservative, evidence-based price contradiction checks.
 * A shared retailer/brand/category is not a shared item/SKU.
 * This deliberately prefers missing an uncertain alert to showing a false one.
 */
final class PriceConflictValidator {
    private PriceConflictValidator() { }

    // A currency marker is mandatory. In particular, "1,059,439회" is not a price.
    private static final Pattern EXPLICIT_PRICE = Pattern.compile(
            "(?:₩\\s*|KRW\\s*)([0-9][0-9,]*)|([0-9][0-9,]*)\\s*원",
            Pattern.CASE_INSENSITIVE
    );
    private static final Set<String> GENERIC_NAMES = Set.of(
            "다이소", "올리브영", "무신사", "쿠팡", "네이버", "이마트", "마트",
            "생활용품", "화장품", "수납함", "바구니", "쿠션", "립밤", "상품", "제품",
            "추천템", "추천상품", "쇼핑", "가성비", "신상", "다이소추천템",
            "다이소상품", "다이소신상", "다이소생활용품", "다이소수납함"
    );
    private static final String[] RETAILERS = { "다이소", "올리브영", "쿠팡", "무신사" };
    private static final String[] BROAD_TYPES = {
            "추천템", "추천상품", "꿀템", "신상", "상품", "제품", "화장품", "생활용품",
            "수납함", "바구니", "화장대", "쿠션", "립밤", "아이템", "가성비"
    };

    static List<String> namedProducts(Object rawDetails) {
        if (!(rawDetails instanceof List<?> details)) return List.of();
        Set<String> products = new LinkedHashSet<>();
        for (Object entry : details) {
            if (!(entry instanceof Map<?, ?> item)) continue;
            if (!"PRODUCT".equalsIgnoreCase(String.valueOf(item.get("type")))) continue;
            Object rawName = item.get("name");
            String name = rawName == null ? "" : String.valueOf(rawName).trim();
            if (!specificName(name)) continue;
            Object confidence = item.get("confidence");
            if (confidence instanceof Number num && num.doubleValue() < 0.45) continue;
            products.add(name);
        }
        return new ArrayList<>(products);
    }

    private static boolean specificName(String name) {
        String compact = compact(name);
        if (compact.length() < 5 || GENERIC_NAMES.contains(compact)) return false;
        for (String retailer : RETAILERS) {
            if (compact.startsWith(retailer)) {
                String remainder = compact.substring(retailer.length());
                for (String broad : BROAD_TYPES) {
                    if (broad.equals(remainder)) return false;
                }
            }
        }
        return true;
    }

    private static String compact(String value) {
        return Normalizer.normalize(value == null ? "" : value, Normalizer.Form.NFKC)
                .toLowerCase(Locale.ROOT).replaceAll("[^\\p{L}\\p{N}]", "");
    }

    private static Set<String> associatedProducts(String claimText, List<String> names) {
        Set<String> result = new LinkedHashSet<>();
        if (names == null || names.isEmpty()) return result;
        String compactText = compact(claimText);
        for (String name : names) {
            if (specificName(name) && compactText.contains(compact(name))) {
                result.add(compact(name));
            }
        }
        // A single identified product per video is an unambiguous fallback.
        // On multi-product list videos, price claims must explicitly name the item.
        if (result.isEmpty() && names.size() == 1 && specificName(names.get(0))) {
            result.add(compact(names.get(0)));
        }
        return result;
    }

    private static Set<Long> explicitAmounts(String text) {
        Set<Long> values = new LinkedHashSet<>();
        Matcher m = EXPLICIT_PRICE.matcher(text == null ? "" : text);
        while (m.find()) {
            String digits = m.group(1) == null ? m.group(2) : m.group(1);
            try {
                long value = Long.parseLong(digits.replace(",", ""));
                if (value > 0) values.add(value);
            } catch (NumberFormatException ignored) { }
        }
        return values;
    }

    private static Long singleAmount(String text) {
        Set<Long> values = explicitAmounts(text);
        return values.size() == 1 ? values.iterator().next() : null;
    }

    static String formattedPrice(String text) {
        Long amount = singleAmount(text);
        return amount == null ? "" : String.format(Locale.KOREA, "%,d원", amount);
    }

    static boolean isContradiction(
            String textA, List<String> productsA, String textB, List<String> productsB
    ) {
        Long priceA = singleAmount(textA);
        Long priceB = singleAmount(textB);
        if (priceA == null || priceB == null || priceA.equals(priceB)) return false;
        Set<String> a = associatedProducts(textA, productsA);
        Set<String> b = associatedProducts(textB, productsB);
        a.retainAll(b);
        return a.size() == 1;
    }
}
