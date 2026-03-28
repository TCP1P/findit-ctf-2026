package main

import "html/template"

type TNote struct {
	ID       string
	Content  template.HTML
	Username string
}

type TPreviewNote struct {
	ID      string
	Preview template.HTML
}

type User struct {
	Username string
	Password string
}
