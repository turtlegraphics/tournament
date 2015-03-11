# Tournament manager
# Bryan Clair Copyright 2013-2015

# Multi-round knockout tournament with possible byes.
# Makes pairings based off of ratings.
# Tracks results, selects next match, updates ratings with ELO.

# The competitors in this tournament are called 'albums' because
# this was written to manage a music play-off.

# Tournament file format:
"""
    # header info
    :tournament <albums> <name>
    :rate spread speed (this line is optional, see ELO_Rater for explanation)
    :round <name> <teams> <byes>
    ...
    :round <name> <teams> <byes>
    # Album definitions
    ALBUMFIRST <rating>
    ...
    ALBUMLAST <rating>
    # Round by round results
    :round <name>
    ALBUMA beat ALBUMB
    ...
"""
# While a tournament <tourn> is in progress, there will be a file
# <tourn>-nextmatch.txt that stores the next match to be played.

import random
import sys
import os.path

class ANSI:
    """ANSI Escape Codes."""
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    BLUE = '\033[34m'
    BRIGHTBLUE = '\033[94m'
    ENDC = '\033[0m'

class ELO_Rater:
    def __init__(self):
        """Implement ELO rating system."""
        self.set_parameters()

    def set_parameters(self,spread=1.0,speed=.2):
        """
        spread : For each spread points of rating advantage, the chance of
                 winning is doubled.
        speed  : ELO's "K-factor", the maximum amount a match can affect
                 the rating.
        """
        self.spread = spread
        self.k = speed
        
    def rate(self,x,y):
        """Return pair of new ratings given ratings of winner x and loser y."""
        qx = 2 ** (x/self.spread)
        qy = 2 ** (y/self.spread)
        Ex = qx/(qx+qy)
        Ey = qy/(qx+qy)
        newx = x + self.k*(1.0 - Ex)
        newy = y + self.k*(0.0 - Ey)
        return (newx,newy)

ELO = ELO_Rater()

class Album:
    """Represents one album."""
    def __init__(self,name,rating,seed=None):
        self.name = name
        self.rating = float(rating)
        self.originalrating = self.rating

        if seed != None:
            self.seed = int(seed)

    def rating(self):
        return self.rating

    def getSeed(self):
        return self.seed

    def setSeed(self,seed):
        self.seed = int(seed)

    def __str__(self):
        return "%3d %s" % (self.seed,self.name)

class Match:
    """Represents a match between entries."""
    def __init__(self,a,b):
        """Entry a vs. entry b.  If b is None, then a has a bye."""
        self.a = a
        self.b = b
        self.winner = None
        self.loser = None
        if self.b == None:
            self.winner = a

    def setWinner(self,winner):
        """Set the winner of this match to winner."""
        if winner == self.a:
            self.winner = self.a
            self.loser = self.b
        else:
            assert winner == self.b
            self.winner = self.b
            self.loser = self.a
        (self.winner.rating,self.loser.rating) = ELO.rate(
            self.winner.rating,self.loser.rating)

    def isMatch(self,t1,t2):
        """True if this is a match between t1 and t2"""
        return (((self.a == t1) and (self.b == t2))
                or ((self.a == t2) and (self.b == t1)))

    def __str__(self):
        out = ''
        if self.winner == self.a:
            out += ANSI.GREEN + str(self.a) + ANSI.BLACK
        elif self.loser == self.a:
            out += ANSI.RED + str(self.a) + ANSI.BLACK
        else:
            out += str(self.a)

        if self.b == None:
            # Bye
            out += ' (bye)'
            return out

        out += ' vs. '
        if self.winner == self.b:
            out += ANSI.GREEN + str(self.b) + ANSI.BLACK
        elif self.loser == self.b:
            out += ANSI.RED + str(self.b) + ANSI.BLACK
        else:
            out += str(self.b)

        return out

class Round:
    """Represents one round in the tournament."""
    def __init__(self,name,numentries,byes=0):
        """
        name is a string identifier for this round.
        numentries is the number of slots in this round.
        byes is the number of byes in this round.
        """
        assert (numentries - byes) % 2 == 0
        self.name = name
        self.size = numentries
        self.byes = byes
        self.matchups = []
        self.paired = False

    def pair(self,entries,sort=None):
        """Fill out the round with a list of albums.
           Entries are sorted by seed if there are byes, by default.
           The sort variable overrides this."""
        assert(not self.paired)
        assert(len(entries) == self.size)
        if self.byes > 0 and sort==None:
            sort = True
        if sort:
            entries.sort(key=Album.getSeed)
        for i in range(self.byes):
            self.matchups.append(Match(entries[i],None))
        for i in range((self.size-self.byes)/2):
            self.matchups.append(
                Match(entries[self.byes + i], entries[self.size-i-1])
                )
        self.paired = True

    def isFinished(self):
        """Returns True if round is finished."""
        if not self.paired:
            return False
        for m in self.matchups:
            if m.winner == None:
                return False
        return True

    def pickMatchup(self):
        """Pick an unresolved matchup."""
        assert(self.paired and not self.isFinished())
        return random.choice([m for m in self.matchups if m.winner == None])

    def match(self,a,b):
        """Return the match between Albums a and b, or None if not found."""
        for m in self.matchups:
            if m.isMatch(a,b):
                return m
        return None

    def winners(self):
        """Return a list of winners, in order."""
        return [m.winner for m in self.matchups if m.winner]
            
    def display(self):
        print 'Round:',self.name
        if not self.paired:
            print '       Not yet paired'
        else:
            for m in self.matchups:
                print m

class Parser:
    """Parse a tournament file.
    Format -
    # header info
    :tournament <albums> <name>
    :rate spread speed (this line is optional, see ELO_Rater for explanation)
    :round <name> <teams> <byes>
    ...
    :round <name> <teams> <byes>
    # Album definitions
    ALBUMFIRST <rating>
    ...
    ALBUMLAST <rating>
    # Round by round results
    :round <name>
    ALBUMA beat ALBUMB
    ...
    """
    def __init__(self,inputfile):
        """Create a parser for an open inputfile."""
        self.f = inputfile
        self.advance()

    def parse(self,tour):
        """Parse the file into the tournament."""
        # Read :tournament record
        (rtype,rval) = self.curRecord()
        assert(rtype == 'tournament')
        trec = rval.split(None,1)
        numalbums = int(trec[0])
        tour.setName(trec[1].rstrip())
        self.advance()

        (rtype,rval) = self.curRecord()

        # Possibly read :rate record
        if rtype == 'rate':
            rrec = rval.split()
            ELO.set_parameters(spread = float(rrec[0]),
                               speed = float(rrec[1]))
            self.advance()

        # Read :round records
        (rtype,rval) = self.curRecord()
        while rtype == 'round':
            rrec = rval.split()
            rname,rmatches,rbyes = rrec[0],int(rrec[1]),int(rrec[2])
            tour.addRound(rname,rmatches,rbyes)
            self.advance()
            (rtype,rval) = self.curRecord()

        # Read album records
        for i in range(numalbums):
            (rtype,rval) = self.curRecord()
            assert(rtype == None)
            self.advance()

            (name,rating) = rval.rsplit(None,1)
            name = name.rstrip()
            rating = float(rating)
            tour.addAlbum(Album(name,rating))

        # Seed the tournament
        tour.seed()

        # Parse results
        (rtype,rval) = self.curRecord()
        while rval:
            assert(rtype == None)
            (w,l) = rval.split('beat')
            (seed,name) = w.split(None,1)
            winner = tour.findAlbum(name.rstrip(),int(seed))
            (seed,name) = l.split(None,1)
            loser = tour.findAlbum(name.rstrip(),int(seed))
            tour.addResult(winner,loser)

            self.advance()
            (rtype,rval) = self.curRecord()

    def curRecord(self):
        """Get a pair (type,data) where type is a string describing
        the type of record, data is the rest of the line. If the line
        is not a record, then type is None and data is the entire line."""
        if self.line == '':
            return (None,None)
        if self.line[0] == ':':
            return self.line[1:].split(None,1)
        return (None,self.line)

    def advance(self):
        """Advance to next line of file.
           Skips whitespace and #comments."""
        self.line = self.f.readline()
        while self.line.strip()=='' or self.line[0] == '#':
            if self.line == '':
                # EOF
                return
            self.line = self.f.readline()

class Tournament:
    """Contains a whole tournament.. albums and rounds."""
    def __init__(self):
        self.albums = []
        self.rounds = []
        self.complete = False
    def seed(self):
        """After all albums and rounds have been added, call this to
        seed the tournament."""
        self.albums.sort(key=Album.rating,reverse=True)
        i = 1
        for a in self.albums:
            a.setSeed(i)
            i += 1

        # From here on, the current round will always be an actual Round
        # (as opposed to a round description)
        self.currentRound = 0
        self.beginRound()
        
    def setName(self,name):
        """Set the human readable name of this tournament."""
        self.name = name

    def addAlbum(self,album):
        """Add a new album to the tournament."""
        self.albums.append(album)

    def addRound(self,rname,rentries,rbyes):
        """Add a new round to the tournament, given it's name,
        the number of entries, and the number of byes."""
        self.rounds.append(Round(rname,rentries,rbyes))

    def beginRound(self):
        """Set up matches for the current round."""
        c = self.currentRound
        if c >= len(self.rounds):
            # Tournament is complete
            self.complete = True
            return
        if c == 0:
            entries = self.albums
        if c > 0:
            assert(self.rounds[c-1].isFinished())
            entries = self.rounds[c-1].winners()
        self.rounds[c].pair(entries)

    def addResult(self,winner,loser):
        """Record that winner beat loser."""
        r = self.rounds[self.currentRound]
        m = r.match(winner,loser)
        m.setWinner(winner)

        if r.isFinished():
            self.currentRound += 1
            self.beginRound()

    def pickMatchup(self):
        """Pick the next matchup to play in the tournament."""
        if self.complete:
            return None
        return self.rounds[self.currentRound].pickMatchup()

    def findAlbum(self,name,seed):
        """Return the album given the seed and name"""
        a = self.albums[seed-1]
        assert a.seed == seed
        assert a.name == name
        return a

    def display(self):
        print self.name
        for r in self.rounds:
            r.display()
        if self.complete:
            print 'Tournament Champion:', self.rounds[-1].winners()[0]

    def displayAlbums(self):
        for a in self.albums:
            out = str(a)+'\t'
            rateout = '%.2f --> %.2f' % (a.originalrating,a.rating)
            if a.originalrating < a.rating:
                out += ANSI.GREEN + rateout + ANSI.BLACK
            if a.originalrating > a.rating:
                out += ANSI.RED + rateout + ANSI.BLACK
            print out

class NextMatch:
    """Class manages the state of the upcoming/current match."""
    def __init__(self,filename):
        self.filename = filename

    def get(self,tour):
        """Return the next pending as a pair of albums, or (None,None)."""
        try:
            f = open(self.filename)
        except:
            return (None,None)

        (a,b) = f.readline().split('vs.')
        (s,n) = a.split(None,1)
        (aseed,aname) = (int(s),n.strip())
        (s,n) = b.split(None,1)
        (bseed,bname) = (int(s),n.strip())
        return (tour.findAlbum(aname,aseed),
                tour.findAlbum(bname,bseed))

    def set(self,m):
        """Set the next pending match to m, or remove the nextmatch file
           if m is None."""
        if m:
            with open(self.filename,'w') as nextfile:
                nextfile.write(str(m))
        else:
            try:
                os.remove(self.filename)
            except:
                pass

if __name__=="__main__":
    # Parse arguments
    import argparse
    aparser = argparse.ArgumentParser()
    aparser.add_argument('tfile',help='tournament data file',
                        type=argparse.FileType('r'))
    aparser.add_argument('-l','--listall',help='list all albums',
                        action='store_true')
    aparser.add_argument('-n','--nextmatch',help='next match record file')
    args = aparser.parse_args()

    # Create and read tournament data
    tourney = Tournament()
    Parser(args.tfile).parse(tourney)

    # Handle results of last match
    #   Compute filename to use, either given by the --nextmatch
    #   argument or else derive it from the tournament file
    #
    if args.nextmatch:
        nextmatchfilename = args.nextmatch
    else:
        (root,ext) = os.path.splitext(args.tfile.name)
        nextmatchfilename = root+'-nextmatch'+ext

    needNewMatch = True
    next = NextMatch(nextmatchfilename)
    (a,b) = next.get(tourney)
    winner = None
    if a and b:
        needNewMatch = False
        print 'Current matchup: ',a,'vs.',b
        try:
            winseed = int(raw_input('Winner? '))
            if a.getSeed() == winseed:
                (winner,loser) = (a,b)
            elif b.getSeed() == winseed:
                (winner,loser) = (b,a)
        except ValueError:
            pass
    if winner:
        tourney.addResult(winner,loser)
        # Write result of the match
        with open(args.tfile.name,'a') as tfile:
            tfile.write(str(winner) + ' beat ' + str(loser) + '\n')

        needNewMatch = True

    if args.listall:
        tourney.displayAlbums()
        print

    tourney.display()

    if needNewMatch:
        # Pick next match
        nextmatch = tourney.pickMatchup()
        next.set(nextmatch)
        if nextmatch:
            print 'Next matchup:',nextmatch
