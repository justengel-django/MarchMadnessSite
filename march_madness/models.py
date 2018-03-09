from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, F, Case, When, Value, Sum
from django.urls import reverse
from django.utils import timezone
from itertools import chain


def validate_year(value):
    if len(str(value)) != 4 or value < 2000:  # Your desired conditions here
        raise ValidationError('Invalid year given %s. The year must be 4 digits and greater than 2000' % value)


def validate_round_match_num(value):
    if value <1:
        raise ValidationError("Number must be greater than 1.")


def current_year():
    """Return the current year."""
    return timezone.now().year


class Team(models.Model):
    name = models.CharField(max_length=255, unique=True)
    icon = models.ImageField(upload_to='MarchMadness/', blank=True)

    def matches(self):
        return chain(self.team1_matches, self.team2_matches)

    def matches_won(self, year=None):
        if year is None:
            year = current_year()
        return chain(self.team1_matches.filter(date__year=year), self.team2_matches.filter(date__year=year))

    def get_seed(self, year=None):
        if year is None:
            year = current_year()

        try:
            return self.rankings.get(year=year).seed
        except:
            return None
    
    def __str__(self):
        return self.name


class TeamRank(models.Model):
    year = models.PositiveIntegerField(default=current_year, validators=[validate_year])
    team = models.ForeignKey(Team, on_delete=models.PROTECT, null=True, blank=True, related_name="rankings")
    seed = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        unique_together = (("year", "team"), ("year", "seed"))
        ordering = ("year", "seed")

    def __str__(self):
        return "".join((str(self.year), " ", self.team.name, " - ", str(self.seed)))


class Tournament(models.Model):
    name = models.CharField(max_length=255, default="March Madness")
    year = models.PositiveIntegerField(default=current_year, validators=[validate_year], unique=True)

    def get_teams(self):
        """Return the teams participating in the tournament."""
        teams = Team.objects.filter(Q(team1_matches__round__in=self.rounds) | Q(team2_matches__round__in=self.rounds))
        return teams.distinct().order_by("rankings__seed", "name")

    def get_user_score(self, user):
        """Return the user score."""
        user_guesses = UserPrediction.objects.filter(user=user, match__round__tournament=self, guess__isnull=False)
        ann = user_guesses.annotate(success=Case(When(Q(guess=F("match__victor")), then=Value(1)),
                                                 default=Value(0), output_field=models.IntegerField()))
        return ann.aggregate(score=Sum("success"))["score"] or 0

    def get_group_score(self, group):
        """Return the group score."""
        value = 0
        for user in group.members.all():
            value += self.get_user_score(user)
        return value

    def __str__(self):
        if str(self.year) not in self.name:
            return " ".join((self.name, str(self.year)))
        return self.name


class Group(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.PROTECT, related_name="groups")
    name = models.CharField(max_length=255)
    captain = models.ForeignKey(get_user_model(), on_delete=models.PROTECT, related_name="captain_for")
    members = models.ManyToManyField(get_user_model(), blank=True, related_name="group")

    class Meta:
        unique_together = ("name", "tournament")

    def __str__(self):
        return self.name


class Round(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.PROTECT, related_name="rounds")
    round_number = models.PositiveIntegerField(validators=[validate_round_match_num])
    name = models.CharField(max_length=255, default="")

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    def next_round(self):
        try:
            return Round.objects.get(tournament=self.tournament, round_number=self.round_number+1)
        except Round.DoesNotExist:
            return None

    def match_names(self):
        return ", ".join((str(match) for match in self.matches.all()))

    class Meta:
        ordering = ("tournament__year", "round_number")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.name:
            self.name = "Round " + str(self.round_number)
        return super(Round, self).save(*args, **kwargs)


class Match(models.Model):
    round = models.ForeignKey(Round, on_delete=models.PROTECT, related_name="matches")
    match_number = models.PositiveIntegerField(validators=[validate_round_match_num])
    date = models.DateTimeField(null=True, blank=True)
    team1 = models.ForeignKey(Team, on_delete=models.PROTECT, null=True, blank=True, related_name="team1_matches")
    team2 = models.ForeignKey(Team, on_delete=models.PROTECT, null=True, blank=True, related_name="team2_matches")
    team1_score = models.PositiveIntegerField(blank=True, null=True)
    team2_score = models.PositiveIntegerField(blank=True, null=True)
    victor = models.ForeignKey(Team, on_delete=models.PROTECT, null=True, blank=True, related_name="match_set_won")

    class Meta:
        unique_together = ("round", "match_number")
        ordering = ("round__round_number", "match_number",)

    # def child_match(self):
    #     try:
    #         next_round = Round.objects.get(tournament=self.round.tournament, round_number=self.round.round_number+1)
    #         return Match.objects.get(Q(teams__in=self.teams), round=next_round)
    #     except (Match.DoesNotExist, Round.DoesNotExist):
    #         pass

    def get_team_choices(self):
        if self.team1 and self.team2:
            return [self.team1, self.team2]

        match1, match2 = self.parent_matches()
        if self.team1:
            team1_choices = [self.team1]
        elif match1 is None:
            team1_choices = Team.objects.all()
        else:
            team1_choices = match1.get_team_choices()

        if self.team2:
            team2_choices = [self.team2]
        elif match2 is None:
            team2_choices = Team.objects.all()
        else:
            team2_choices = match2.get_team_choices()

        return chain(team1_choices, team2_choices)

    def parent_matches(self):
        num = int(self.match_number * 2)
        match_nums = [num - 1, num]
        try:
            match1 = Match.objects.get(round__round_number=self.round.round_number-1, match_number=match_nums[0])
        except Match.DoesNotExist:
            match1 = None

        try:
            match2 = Match.objects.get(round__round_number=self.round.round_number-1, match_number=match_nums[1])
        except Match.DoesNotExist:
            match2 = None
        return match1, match2

    def prediction(self, user):
        return self.user_prediction.get(user=user)

    def get_absolute_url(self):
        return reverse('march_madness:round', args=[self.id])

    def __str__(self):
        if self.round:
            return "Round " + str(self.round.round_number) + " Match " + str(self.match_number)
        return "Match " + str(self.match_number)


class UserPrediction(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.PROTECT)
    match = models.ForeignKey(Match, on_delete=models.PROTECT, related_name="user_prediction")

    guess = models.ForeignKey(Team, on_delete=models.PROTECT)
    team1_score = models.PositiveIntegerField(null=True, blank=True, verbose_name="Team 1 Score")
    team2_score = models.PositiveIntegerField(null=True, blank=True, verbose_name="Team 2 Score")

    def guessed_right(self):
        """Return if the guess was correct. Return None if a match victor has not been set yet."""
        if self.match.victor:
            return self.match.victor == self.guess
        return None

    class Meta:
        unique_together = ("user", "match")
        ordering = ("match__date", )

    def check_date(self):
        if self.match.round.start_date and self.match.round.start_date < timezone.now():
            raise ValidationError("You cannot set or change a prediction after the round has started!")