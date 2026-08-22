package main

import (
	"crypto/rand"
	"html/template"
	"math/big"
	"regexp"
	"sort"
	"strings"

	"github.com/gin-contrib/sessions"
	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
)

var metaTagPattern = regexp.MustCompile(`(?is)<meta\b[^>]*>`)
var previewTagReplacer = strings.NewReplacer(
	"&lt;b&gt;", "<b>",
	"&lt;/b&gt;", "</b>",
	"&lt;strong&gt;", "<strong>",
	"&lt;/strong&gt;", "</strong>",
	"&lt;i&gt;", "<i>",
	"&lt;/i&gt;", "</i>",
	"&lt;em&gt;", "<em>",
	"&lt;/em&gt;", "</em>",
	"&lt;u&gt;", "<u>",
	"&lt;/u&gt;", "</u>",
	"&lt;code&gt;", "<code>",
	"&lt;/code&gt;", "</code>",
	"&lt;pre&gt;", "<pre>",
	"&lt;/pre&gt;", "</pre>",
	"&lt;br&gt;", "<br>",
	"&lt;br/&gt;", "<br>",
	"&lt;br /&gt;", "<br>",
	"&lt;p&gt;", "<p>",
	"&lt;/p&gt;", "</p>",
)

func generateID() string {
	return uuid.New().String()
}

// Helper function to get username from the context
func getUsernameFromContext(c *gin.Context) string {
	session := sessions.Default(c)
	username := session.Get("username")
	return username.(string)
}

// Helper function to search user's notes based on the query
func getNotesByContent(username, query string) []TNote {
	var result []TNote
	for _, note := range Notes {
		if note.Username == username && containsIgnoreCase(string(note.Content), query) {
			result = append(result, note)
		}
	}

	sort.Slice(result, func(i, j int) bool {
		return result[i].Content < result[j].Content
	})

	for i, note := range result {
		if containsIgnoreCase(string(note.Content), "<!--managed-->") {
			result = append(result[:i], result[i+1:]...)
		}
	}
	return result
}

// Helper function to check if a string contains another string (case-insensitive)
func containsIgnoreCase(s, substr string) bool {
	return strings.Contains(strings.ToLower(s), strings.ToLower(substr))
}

func getNoteById(id string) *TNote {
	for _, n := range Notes {
		if n.ID == id {
			return &n
		}
	}
	return nil
}

func extractMetaTags(content template.HTML) template.HTML {
	matches := metaTagPattern.FindAllString(string(content), -1)
	return template.HTML(strings.Join(matches, ""))
}

// Legacy formatting preview preserves a tiny allowlist of inline tags for imported notes.
// The output is re-escaped first so event handlers, attributes, and unsupported tags cannot survive.
func renderLegacyPreview(content template.HTML) template.HTML {
	escaped := template.HTMLEscapeString(string(content))
	return template.HTML(previewTagReplacer.Replace(escaped))
}

func buildPreviewNotes(notes []TNote) []TPreviewNote {
	result := make([]TPreviewNote, 0, len(notes))
	for _, note := range notes {
		result = append(result, TPreviewNote{
			ID:      note.ID,
			Preview: renderLegacyPreview(note.Content),
		})
	}
	return result
}

// GenerateRandomString generates a random string of length n
func GenerateRandomString(n int) (string, error) {
	const letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
	// Get the length of the letters string
	letterLen := big.NewInt(int64(len(letters)))

	randomString := make([]byte, n)
	for i := range randomString {
		// Generate a random index using cryptographic randomness
		randomIndex, err := rand.Int(rand.Reader, letterLen)
		if err != nil {
			return "", err
		}
		// Use the random index to select a character from the letters string
		randomString[i] = letters[randomIndex.Int64()]
	}
	return string(randomString), nil
}
