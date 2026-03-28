package main

import (
	"net/http"
	"sync"

	"github.com/gin-contrib/sessions"
	"github.com/gin-contrib/sessions/cookie"
	"github.com/gin-gonic/gin"
)

var (
	users      []User
	usersMutex sync.Mutex
)

var (
	Notes      []TNote
	notesMutex sync.Mutex
)
var key, _ = GenerateRandomString(32)
var store = cookie.NewStore([]byte(key))

func main() {
	router := gin.Default()

	router.LoadHTMLGlob("./views/*")
	router.Static("/assets", "./assets")

	store.Options(sessions.Options{
		Path:     "/",
		MaxAge:   3600,
		HttpOnly: true,
		SameSite: http.SameSiteDefaultMode,
	})

	router.Use(sessions.Sessions("session", store))
	router.Use(CSPMiddleware())

	router.GET("/login", func(c *gin.Context) {
		c.HTML(http.StatusOK, "login.html", nil)
	})
	router.POST("/login", login)
	router.GET("/register", func(c *gin.Context) {
		c.HTML(http.StatusOK, "register.html", nil)
	})
	router.POST("/register", register)

	router.Use(checkLoginMiddleware())

	router.GET("/", func(c *gin.Context) {
		c.HTML(http.StatusOK, "index.html", nil)
	})

	router.GET("/logout", logout)
	router.GET("/notes", viewNotes)
	router.GET("/note/:id", getNote)
	router.POST("/create-note", createNote)
	router.GET("/delete-note/:id", deleteNote)

	router.GET("/search-notes", searchNotes)

	router.Run(":80")
}

// Middleware to check if the user is logged in
func checkLoginMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		session := sessions.Default(c)
		username := session.Get("username")

		// If the user is not logged in, redirect to the login page
		if username == nil {
			c.Redirect(http.StatusSeeOther, "/login")
			c.Abort()
			return
		}

		c.Next()
	}
}

func CSPMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; img-src 'self' data:; form-action 'self'; base-uri 'none'; frame-src https://www.youtube.com https://www.youtube-nocookie.com;")
		c.Header("Permissions-Policy", "autoplay=(self \"https://www.youtube.com\")")
		c.Next()
	}
}
