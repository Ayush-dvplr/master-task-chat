cd "/Users/mac/Desktop/Terminal Bench/_runs/20261031/flood-repair-portfolio/fixgate-20261031T121057-69b5/jobs"
perl -e 'alarm 2400; exec @ARGV' harbor run --path "/Users/mac/Desktop/Terminal Bench/_runs/20261031/flood-repair-portfolio/fixgate-20261031T121057-69b5/copies/owner" --agent oracle --env docker --job-name owner-1 --jobs-dir "/Users/mac/Desktop/Terminal Bench/_runs/20261031/flood-repair-portfolio/fixgate-20261031T121057-69b5/jobs" -y; echo "owner-1 rc $?"
echo LANE_DONE
