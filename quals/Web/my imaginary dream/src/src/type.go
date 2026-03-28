package main

import "html/template"

type TNote struct {
	ID       string
	Content  template.HTML
	Username string
}
type User struct {
	Username string
	Password string
}
