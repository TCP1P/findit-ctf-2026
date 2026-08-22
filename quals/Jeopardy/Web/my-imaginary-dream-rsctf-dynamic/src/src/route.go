package main

import (
	"html/template"
	"net/http"
	"strings"

	"github.com/gin-contrib/sessions"
	"github.com/gin-gonic/gin"
)

func login(c *gin.Context) {
	username := c.PostForm("username")
	password := c.PostForm("password")

	var foundUser *User
	for _, user := range users {
		if user.Username == username && user.Password == password {
			foundUser = &user
			break
		}
	}

	if foundUser != nil {
		session := sessions.Default(c)
		session.Set("username", foundUser.Username)
		session.Save()

		c.Redirect(http.StatusSeeOther, "/notes")
	} else {
		c.HTML(http.StatusUnauthorized, "login.html", gin.H{"Error": "Invalid credentials"})
	}
}

func register(c *gin.Context) {
	username := c.PostForm("username")
	password := c.PostForm("password")

	newUser := User{
		Username: username,
		Password: password,
	}

	usersMutex.Lock()
	users = append(users, newUser)
	defer usersMutex.Unlock()

	c.Redirect(http.StatusSeeOther, "/login")
}

func logout(c *gin.Context) {
	session := sessions.Default(c)
	session.Clear()
	session.Save()

	c.Redirect(http.StatusSeeOther, "/login")
}

func viewNotes(c *gin.Context) {
	// Retrieve the current user from the session
	username := getUsernameFromContext(c)

	// Filter notes based on the current user
	userNotes := make([]TNote, 0)
	for _, note := range Notes {
		if note.Username == username {
			userNotes = append(userNotes, note)
		}
	}

	c.HTML(http.StatusOK, "notes.html", gin.H{
		"Notes": userNotes,
	})
}

func getNote(c *gin.Context) {
	id := c.Param("id")
	note := getNoteById(id)
	c.HTML(http.StatusOK, "note.html", gin.H{
		"Note":      note,
		"HeadMetas": extractMetaTags(note.Content),
	})
}

func createNote(c *gin.Context) {
	content := c.PostForm("content")

	// Retrieve the current user from the session
	username := getUsernameFromContext(c)

	newNote := TNote{
		ID:       generateID(),
		Content:  template.HTML(content),
		Username: username,
	}

	notesMutex.Lock()
	Notes = append(Notes, newNote)
	defer notesMutex.Unlock()

	c.Redirect(http.StatusSeeOther, "/notes")
}

func deleteNote(c *gin.Context) {
	id := c.Param("id")

	for i, note := range Notes {
		if note.ID == id {
			notesMutex.Lock()
			Notes = append(Notes[:i], Notes[i+1:]...)
			defer notesMutex.Unlock()
			break
		}
	}

	c.Redirect(http.StatusSeeOther, "/notes")
}

func searchNotes(c *gin.Context) {
	username := getUsernameFromContext(c) // Get the username from the context

	// Retrieve the search query from the URL query parameters
	query := c.Query("query")

	// Preview mode keeps note reviews consistent for imported formatting.
	if strings.HasPrefix(query, "preview:") {
		query = query[8:]
		userNotes := getNotesByContent(username, query)

		c.HTML(http.StatusOK, "preview-results.html", gin.H{
			"Query": query,
			"Notes": buildPreviewNotes(userNotes),
		})
		return
	}

	// Redirect mode is retained for older clients that open a single match directly.
	if strings.HasPrefix(query, "view:") {
		query = query[5:]
		userNotes := getNotesByContent(username, query)

		if len(userNotes) == 0 {
			c.HTML(http.StatusOK, "search-results.html", gin.H{
				"Query": query,
				"Notes": userNotes,
			})
			return
		}

		c.Redirect(http.StatusSeeOther, "/note/"+userNotes[0].ID)
		return
	}
	// Search user's notes for the given query
	userNotes := getNotesByContent(username, query)

	c.HTML(http.StatusOK, "search-results.html", gin.H{
		"Query": query,
		"Notes": userNotes,
	})
}
