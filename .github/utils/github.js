const fs = require("fs");

function uploadReleaseArtifacts({ github, context }) {
  const tag = fs.readFileSync("release_version.txt").toString().trim();
  const { owner, repo } = context.repo;

  const artifacts = fs
    .readdirSync("dist")
    .filter((f) => f.endsWith(".whl") || f.endsWith(".tar.gz"));
  const release_id = github.rest.repos.getReleaseByTag({ owner, repo, tag })
    .data.id;

  artifacts.forEach((name) => {
    const data = fs.readFileSync(`dist/${name}`);
    github.rest.repos.uploadReleaseAsset({
      owner,
      repo,
      release_id,
      name,
      data,
    });
  });
}

function commentReleaseNotes({ github, context }) {
  const versionNumber = fs
    .readFileSync("release_version.txt")
    .toString()
    .trim();
  const releaseNotes = fs.readFileSync("release_notes.txt").toString().trim();

  const commentBody = `Merging this PR will release \`${versionNumber}\` with the following release notes:\n\n${releaseNotes}`;

  github.rest.issues.createComment({
    issue_number: context.issue.number,
    owner: context.repo.owner,
    repo: context.repo.repo,
    body: commentBody,
  });
}

module.exports = { uploadReleaseArtifacts, commentReleaseNotes };
