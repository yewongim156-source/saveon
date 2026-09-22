package com.saveon.api.content.dto;

import com.saveon.api.content.ContentPlatform;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

public record CreateContentRequest(

        @NotBlank
        String sourceUrl,

        @NotNull
        ContentPlatform platform
) {
}