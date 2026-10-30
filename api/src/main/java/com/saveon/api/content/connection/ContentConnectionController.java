package com.saveon.api.content.connection;

import com.saveon.api.content.Content;
import com.saveon.api.content.connection.dto.ContentConnectionResponse;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v1/content-connections")
@CrossOrigin(origins = "*")
public class ContentConnectionController {

    private final ContentConnectionService contentConnectionService;

    public ContentConnectionController(
            ContentConnectionService contentConnectionService
    ) {
        this.contentConnectionService = contentConnectionService;
    }

    @GetMapping
    public List<ContentConnectionResponse> findConnections(
            @RequestParam(name = "type", required = false) String type,
            @RequestParam(name = "limit", required = false) Integer limit
    ) {
        return contentConnectionService.findConnections(type, limit);
    }

    @GetMapping("/contents")
    public List<Content> findConnectedContents(
            @RequestParam(name = "type") String type,
            @RequestParam(name = "entity") String entity
    ) {
        return contentConnectionService.findConnectedContents(type, entity);
    }
}
