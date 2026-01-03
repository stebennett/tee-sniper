package clients

import (
	"fmt"
	"log/slog"
	"math/rand"
	"net/http"
	"net/http/cookiejar"
	"net/url"
	"regexp"
	"strconv"
	"strings"

	"github.com/PuerkitoBio/goquery"
	"github.com/stebennett/tee-sniper/pkg/models"
)

var (
	loginUrl        = "login.php"
	teeAvailability = "memberbooking/"
	book            = "memberbooking/"
	userAgents      = []string{
		"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
		"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
		"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
		"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
		"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
	}
)

type BookingClient struct {
	baseUrl   string
	httpClient *http.Client
	userAgent string
}

func NewBookingClient(u string) (*BookingClient, error) {
	jar, err := cookiejar.New(nil)
	if err != nil {
		return nil, err
	}

	client := &http.Client{
		Jar: jar,
	}

	// Select a random user agent for this session
	selectedUserAgent := userAgents[rand.Intn(len(userAgents))]

	return &BookingClient{
		baseUrl:   u,
		httpClient: client,
		userAgent: selectedUserAgent,
	}, nil
}

func (w *BookingClient) addBrowserHeaders(req *http.Request) {
	req.Header.Set("User-Agent", w.userAgent)
	req.Header.Set("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
	req.Header.Set("Accept-Language", "en-US,en;q=0.5")
	req.Header.Set("Accept-Encoding", "gzip, deflate")
	req.Header.Set("Connection", "keep-alive")
	req.Header.Set("Upgrade-Insecure-Requests", "1")
}

func (w BookingClient) Login(username string, password string) (bool, error) {
	form := url.Values{}
	form.Add("task", "login")
	form.Add("topmenu", "1")
	form.Add("memberid", username)
	form.Add("pin", password)
	form.Add("cachemid", "1")
	form.Add("Submit", "Login")

	url := fmt.Sprintf("%s%s", w.baseUrl, loginUrl)

	req, err := http.NewRequest("POST", url, strings.NewReader(form.Encode()))
	if err != nil {
		return false, err
	}

	w.addBrowserHeaders(req)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")

	resp, err := w.httpClient.Do(req)
	if err != nil {
		return false, err
	}

	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return false, nil
	}

	doc, err := goquery.NewDocumentFromReader(resp.Body)
	if err != nil {
		return true, err
	}

	pageTitle := doc.Find("title").Text()
	return strings.HasPrefix(pageTitle, "Welcome"), nil
}

func (w BookingClient) GetCourseAvailability(dateStr string) ([]models.TimeSlot, error) {
	slots := []models.TimeSlot{}

	url := fmt.Sprintf("%s%s", w.baseUrl, teeAvailability)
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return slots, err
	}

	w.addBrowserHeaders(req)
	q := req.URL.Query()
	q.Add("date", dateStr)
	req.URL.RawQuery = q.Encode()

	resp, err := w.httpClient.Do(req)
	if err != nil {
		return slots, err
	}

	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return slots, fmt.Errorf("invalid status code returned %d", resp.StatusCode)
	}

	doc, err := goquery.NewDocumentFromReader(resp.Body)
	if err != nil {
		return slots, err
	}

	doc.Find("tr.canreserve,tr.cantreserve").Each(func(i int, s *goquery.Selection) {
		bookingButton := s.Find("a.inlineBooking").Length() != 0
		peopleBooked := s.Find("span.player-name").Length() != 0
		blocked := s.Find("div.comp-item").Length() != 0
		time := s.Find("th").Text()

		bookingForm := make(map[string]string)
		s.Find("td.slot-actions form input").Each(func(i int, q *goquery.Selection) {
			name, nok := q.Attr("name")
			value, vok := q.Attr("value")
			if nok && vok {
				bookingForm[name] = value
			}
		})

		if !peopleBooked && !blocked && bookingButton {
			slots = append(slots, models.TimeSlot{
				Time:        time,
				BookingForm: bookingForm,
				CanBook:     bookingButton,
			})
		}
	})

	return slots, nil
}

func (w BookingClient) BookTimeSlot(timeSlot models.TimeSlot, playingPartners []string, dryRun bool) (string, error) {
	numSlots := len(playingPartners) + 1 // +1 for the main player

	url := fmt.Sprintf("%s%s", w.baseUrl, book)
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return "", err
	}

	w.addBrowserHeaders(req)
	q := req.URL.Query()

	// First add all booking form parameters
	for k, v := range timeSlot.BookingForm {
		q.Add(k, v)
	}

	// Then set/override the numslots parameter
	q.Set("numslots", strconv.Itoa(numSlots))

	req.URL.RawQuery = q.Encode()

	slog.Debug("booking request", slog.String("url", req.URL.String()))
	if dryRun {
		slog.Info("dry run: booking simulated",
			slog.String("time", timeSlot.Time),
			slog.Int("players", numSlots),
			slog.Bool("dry_run", true),
		)
		return "dryrun-booking-id", nil
	}

	resp, err := w.httpClient.Do(req)
	if err != nil {
		return "", err
	}

	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return "", fmt.Errorf("invalid status code returned %d", resp.StatusCode)
	}

	doc, err := goquery.NewDocumentFromReader(resp.Body)
	if err != nil {
		return "", err
	}

	confirmation := doc.Find("#globalwrap > div.user-messages.alert.user-message-success.alert-success > ul > li > strong").Text()
	if strings.Compare(confirmation, "Now please enter the names of your playing partners.") != 0 {
		return "", fmt.Errorf("booking failed: unexpected confirmation message: %s", confirmation)
	}

	// Extract booking ID from the current URL
	bookingID, err := w.extractBookingID(resp.Request.URL.String())
	if err != nil {
		return "", fmt.Errorf("failed to extract booking ID: %v", err)
	}

	return bookingID, nil
}

func (w BookingClient) extractBookingID(urlStr string) (string, error) {
	// Extract booking ID from URL like hostname/memberbooking/?edit=<bookingid>&...
	re := regexp.MustCompile(`[?&]edit=([^&]+)`)
	matches := re.FindStringSubmatch(urlStr)
	if len(matches) < 2 {
		return "", fmt.Errorf("booking ID not found in URL: %s", urlStr)
	}
	return matches[1], nil
}

func (w BookingClient) AddPlayingPartner(bookingID, partnerID string, slotNumber int, dryRun bool) error {
	url := fmt.Sprintf("%s%s", w.baseUrl, book)
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return err
	}

	w.addBrowserHeaders(req)
	q := req.URL.Query()
	q.Add("edit", bookingID)
	q.Add("addpartner", partnerID)
	q.Add("partnerslot", strconv.Itoa(slotNumber))
	req.URL.RawQuery = q.Encode()

	slog.Debug("adding partner request", slog.String("url", req.URL.String()))
	if dryRun {
		slog.Info("dry run: partner addition simulated",
			slog.String("partner_id", partnerID),
			slog.Int("slot", slotNumber),
			slog.String("booking_id", bookingID),
			slog.Bool("dry_run", true),
		)
		return nil
	}

	resp, err := w.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return fmt.Errorf("failed to add partner: status code %d", resp.StatusCode)
	}

	return nil
}
