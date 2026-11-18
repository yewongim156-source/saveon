package com.saveon.api.ai;

import java.util.List;

public record AiEmbedResponse(
        String model,
        int dimensions,
        List<Float> vector
) {
    public float[] asArray() {
        if (vector == null) {
            return new float[0];
        }

        float[] result = new float[vector.size()];
        for (int index = 0; index < vector.size(); index++) {
            result[index] = vector.get(index);
        }
        return result;
    }
}
